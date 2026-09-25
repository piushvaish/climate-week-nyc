"""Produce genuine, comparable 2022–2026 Calcatreu Landsat observations.

25 km square screening window; 200 m analysis grid; August–September scenes.
This is a vegetation screen, never a forest-loss or mining-causation estimate.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
if sys.version_info[:2] == (3, 12) and (ROOT / 'python_packages312').exists():
    sys.path.insert(0, str(ROOT / 'python_packages312'))
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO, RawIOBase
import json
import math
from urllib.parse import urlsplit, urlunsplit
import time
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds
from pyproj import Transformer
from PIL import Image
import requests

OUT = ROOT / 'data' / 'calcatreu'
OUT.mkdir(parents=True, exist_ok=True)
CA = ROOT / 'data' / 'trusted-ca.pem'
VERIFY = str(CA) if CA.exists() else True
CRS = 'EPSG:32719'
CELL = 200
SIZE = 125
POINT = [-69.4225, -41.7316667]
to_grid = Transformer.from_crs(4326, CRS, always_xy=True)
to_geo = Transformer.from_crs(CRS, 4326, always_xy=True)
CX, CY = to_grid.transform(*POINT)
LEFT, BOTTOM, RIGHT, TOP = CX-12500, CY-12500, CX+12500, CY+12500
GRID = from_origin(LEFT, TOP, CELL, CELL)
SHAPE = (SIZE, SIZE)
SAS = {}


def sign(href):
    parts = urlsplit(href)
    key = (parts.netloc, parts.path.split('/')[1])
    if key not in SAS:
        for attempt in range(7):
            r = requests.get('https://planetarycomputer.microsoft.com/api/sas/v1/sign',
                             params={'href': href}, verify=VERIFY, timeout=60)
            if r.status_code == 429:
                time.sleep(min(5 * (attempt + 1), 30))
                continue
            r.raise_for_status()
            SAS[key] = urlsplit(r.json()['href']).query
            break
        else:
            raise RuntimeError('Planetary Computer signer rate limited; try again later.')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, SAS[key], ''))


class VerifiedRangeFile(RawIOBase):
    """TLS-verified range reads for GDAL builds with incompatible TLS backends."""
    block_size=1024*1024

    def __init__(self, href):
        super().__init__()
        self.href=href
        self.position=0
        self.blocks={}
        self.session=requests.Session()
        r=self.session.head(href,verify=VERIFY,timeout=60)
        r.raise_for_status()
        self.length=int(r.headers['Content-Length'])

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        self.position=(0 if whence==0 else self.position if whence==1 else self.length)+offset
        if self.position<0: raise ValueError('Negative file position')
        return self.position

    def read(self, size=-1):
        end=self.length if size<0 else min(self.length,self.position+size)
        output=[]
        while self.position<end:
            block=self.position//self.block_size
            start=block*self.block_size
            if block not in self.blocks:
                r=self.session.get(self.href,headers={'Range':f'bytes={start}-{min(self.length-1,start+self.block_size-1)}'},verify=VERIFY,timeout=90)
                if r.status_code!=206: raise RuntimeError('Expected HTTP partial-content response')
                self.blocks[block]=r.content
            count=min(end-self.position,len(self.blocks[block])-(self.position-start))
            if count<=0: break
            output.append(self.blocks[block][self.position-start:self.position-start+count])
            self.position+=count
        return b''.join(output)

    def close(self):
        self.session.close()
        super().close()


def read_asset(args):
    name, href = args
    # The custom opener retains certificate verification and downloads only needed blocks.
    filename=urlsplit(href).path.rsplit('/',1)[-1]
    def opener(path,mode='rb'):
        if str(path)!=filename: raise FileNotFoundError(path)
        return VerifiedRangeFile(href)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
        with rasterio.open(filename,opener=opener) as src:
            bounds = transform_bounds(CRS, src.crs, LEFT, BOTTOM, RIGHT, TOP, densify_pts=21)
            win = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
            return name, (src.read(1, window=win, boundless=True, fill_value=src.nodata or 0),
                          src.window_transform(win), src.crs)


def aggregate(array, transform, crs):
    dst = np.full(SHAPE, np.nan, dtype='float32')
    reproject(array.astype('float32'), dst, src_transform=transform, src_crs=crs,
              dst_transform=GRID, dst_crs=CRS, src_nodata=np.nan, dst_nodata=np.nan,
              resampling=Resampling.average)
    return dst


def scene_data(scene):
    cache = OUT / (scene['id'] + '.npz')
    if cache.exists():
        return dict(np.load(cache))
    names = ['red', 'green', 'blue', 'nir08', 'swir22', 'qa_pixel', 'qa_radsat']
    assets = [(name, sign(scene['assets'][name]['href'])) for name in names]
    with ThreadPoolExecutor(max_workers=4) as pool:
        bands = dict(pool.map(read_asset, assets))
    transform, crs = bands['red'][1:]
    assert all(bands[k][0].shape == bands['red'][0].shape and bands[k][1] == transform for k in names)
    qa = bands['qa_pixel'][0].astype('uint16')
    # Fill, dilated cloud, cirrus, cloud, shadow, snow, water and any saturation.
    bad_bits = sum(1 << bit for bit in [0, 1, 2, 3, 4, 5, 7])
    good = ((qa & bad_bits) == 0) & (bands['qa_radsat'][0] == 0)
    sr = {}
    for name in ['red', 'green', 'blue', 'nir08', 'swir22']:
        raw = bands[name][0]
        sr[name] = raw.astype('float32') * 0.0000275 - 0.2
    good &= np.logical_and.reduce([(bands[k][0] != 0) & (sr[k] > 0) & (sr[k] < 1.1) for k in ['red','nir08','swir22']])
    fraction = aggregate(good.astype('float32'), transform, crs)
    valid = fraction >= 0.80
    indices = {}
    for metric, other in [('ndvi','red'), ('nbr','swir22')]:
        denominator = sr['nir08'] + sr[other]
        source = np.divide(sr['nir08']-sr[other], denominator,
                           out=np.full_like(denominator, np.nan), where=good & (denominator > 0.01))
        indices[metric] = np.where(valid, aggregate(source, transform, crs), np.nan)
    # True-colour image on a finer 800 x 800 projected grid, with the same stretch across dates.
    rgb = []
    photo_grid = from_origin(LEFT, TOP, 25000/800, 25000/800)
    for name in ['red','green','blue']:
        dst = np.full((800,800), np.nan, dtype='float32')
        source = np.where(good, sr[name], np.nan)
        reproject(source, dst, src_transform=transform, src_crs=crs, dst_transform=photo_grid,
                  dst_crs=CRS, src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
        rgb.append(np.clip((dst - 0.015) / 0.30, 0, 1) ** 0.8)
    image = np.stack(rgb, axis=-1)
    image = np.where(np.isfinite(image), image, 0)
    indices['rgb'] = (image * 255).astype('uint8')
    indices['valid'] = valid
    np.savez_compressed(cache, **indices)
    return indices


def encode(array):
    a = np.where(np.isfinite(array), np.rint(array * 10000), -32768).astype('<i2')
    return base64.b64encode(a.tobytes()).decode('ascii')


def main():
    snapshots, matrices = [], {}
    for year in range(2022, 2027):
        catalog = json.loads((ROOT / 'data' / f'calcatreu-stac-{year}.json').read_text())
        candidates = [s for s in catalog['features'] if s['id'].startswith(('LC08_', 'LC09_'))
                      and str(s['properties']['landsat:wrs_path']) == '230'
                      and str(s['properties']['landsat:wrs_row']) == '089']
        candidates.sort(key=lambda s: s['properties'].get('eo:cloud_cover',100))
        best = None
        # Scene cloud fraction is not local cloud fraction: check local QA coverage.
        for scene in candidates[:3]:
            values = scene_data(scene)
            coverage = float(np.isfinite(values['ndvi']).mean())
            if best is None or coverage > best[0]:
                best = coverage, scene, values
            if coverage >= .95:
                break
        if best is None:
            raise RuntimeError(f'No suitable scene for {year}')
        coverage, scene, values = best
        scene_date = scene['properties']['datetime'][:10]
        for metric in ['ndvi','nbr']:
            matrices[f'{metric}{year}'] = values[metric]
        jpg = BytesIO()
        Image.fromarray(values['rgb']).save(jpg, format='JPEG', quality=80, optimize=True)
        snapshots.append({'year':year, 'date':scene_date, 'id':scene['id'],
                          'sensor':scene['properties']['platform'], 'coverage':round(coverage,4),
                          'cloudPercent':scene['properties'].get('eo:cloud_cover'),
                          'url':'https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2/items/'+scene['id'],
                          'image':'data:image/jpeg;base64,'+base64.b64encode(jpg.getvalue()).decode('ascii')})
        (OUT / f'scene-{year}.json').write_text(json.dumps(scene), encoding='utf-8')
        print(f'{year}: {scene_date} | local clear coverage {coverage:.1%}', flush=True)
    common = np.logical_and.reduce([np.isfinite(matrices[f'ndvi{year}']) for year in range(2022,2027)])
    baseline = matrices['ndvi2022']
    vegetated = common & (baseline >= .2)
    summary = []
    for year in range(2022,2027):
        current = matrices[f'ndvi{year}']
        retained = vegetated & (current >= .2)
        decline = vegetated & (current-baseline < -.1)
        summary.append({'year':year,'baselineVegetationHa':int(vegetated.sum())*4,
                        'retainedHa':int(retained.sum())*4,
                        'retainedPercent':round(100*retained.sum()/max(1,vegetated.sum()),1),
                        'declineHa':int(decline.sum())*4,
                        'meanNdvi':round(float(current[common].mean()),4)})
    doc = {'version':1,'generatedAt':datetime.now(timezone.utc).isoformat(),
           'location':{'name':'Calcatreu','province':'Río Negro, Argentina','point':POINT,
                       'scope':'25 × 25 km study window; not a mine or concession boundary'},
           'width':SIZE,'height':SIZE,'cellSizeM':CELL,'cellAreaHa':4,'areaHa':62500,
           'epsg':32719,'bounds':[LEFT,BOTTOM,RIGHT,TOP],
           'corners':[list(to_geo.transform(x,y)) for x,y in [(LEFT,TOP),(RIGHT,TOP),(RIGHT,BOTTOM),(LEFT,BOTTOM)]],
           'baselineYear':2022,'baselineNdvi':.2,'declineThreshold':-.1,
           'commonCells':int(common.sum()),'commonCoverage':round(float(common.mean()),4),
           'commonMask':base64.b64encode(common.astype('uint8').tobytes()).decode('ascii'),
           'scenes':snapshots,'summary':summary,'arrays':{k:encode(v) for k,v in matrices.items()},
           'method':'One QA-masked August–September Landsat 8/9 scene per year, 30 m reflectance averaged to 200 m cells. All years use the same valid-cell support. Baseline NDVI ≥0.20; decline is ΔNDVI <−0.10. This screen is not a forest classification or a causal attribution.',
           'sources':[{'label':'USGS Landsat via Planetary Computer','url':'https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2'},
                      {'label':'QA_PIXEL and saturation flags','url':'https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands'},
                      {'label':'Government project coordinate','url':'https://www.argentina.gob.ar/sites/default/files/catalogo_de_proyectos_avanzados_de_oro-espanol.pdf'}]}
    (OUT/'satellite.json').write_text(json.dumps(doc,separators=(',',':')),encoding='utf-8')
    with rasterio.open(OUT/'indices-200m.tif','w',driver='GTiff',height=SIZE,width=SIZE,count=10,
                       dtype='float32',crs=CRS,transform=GRID,nodata=-9999,compress='deflate') as dst:
        for band,(name,values) in enumerate(matrices.items(),1):
            dst.write(np.where(np.isfinite(values),values,-9999),band)
            dst.set_band_description(band,name)
    print('Common support',int(common.sum()),'/',SIZE*SIZE, 'cells; baseline vegetation', int(vegetated.sum())*4,'ha',flush=True)


if __name__ == '__main__':
    main()
