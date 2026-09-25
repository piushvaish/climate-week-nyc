"""Discover public Landsat scenes around the sourced Calcatreu coordinate."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'python_packages312'))
import requests

root = Path(__file__).parent
(root / 'data').mkdir(exist_ok=True)
ca = root / 'data' / 'trusted-ca.pem'
bbox = [-69.58, -41.86, -69.27, -41.60]
for year in range(2022, 2027):
    path = root / 'data' / f'calcatreu-stac-{year}.json'
    if not path.exists():
        response = requests.get('https://planetarycomputer.microsoft.com/api/stac/v1/search', params={
            'collections': 'landsat-c2-l2', 'bbox': ','.join(map(str, bbox)),
            'datetime': f'{year}-08-01T00:00:00Z/{year}-09-25T23:59:59Z', 'limit': 100,
        }, verify=str(ca) if ca.exists() else True, timeout=60)
        response.raise_for_status()
        path.write_text(json.dumps(response.json()), encoding='utf-8')
    scenes = json.loads(path.read_text())['features']
    scenes.sort(key=lambda s: s['properties'].get('eo:cloud_cover', 100))
    print(year, 'candidates', len(scenes), flush=True)
    for s in scenes[:5]:
        print(s['id'], s['properties']['datetime'], s['properties'].get('eo:cloud_cover'),
              s['properties'].get('landsat:wrs_path'), s['properties'].get('landsat:wrs_row'), flush=True)
    if year == 2026 and scenes:
        print('assets', list(scenes[0]['assets']), flush=True)
