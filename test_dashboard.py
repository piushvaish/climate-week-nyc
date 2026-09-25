"""Meaningful checks for comparable areas, source dates and local API boundaries."""
import base64
import json
from pathlib import Path
import struct
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError

import dashboard_server
from news_service import normalize_results, safe_url

ROOT = Path(__file__).resolve().parent
# These tests only contact an ephemeral loopback server, never an external proxy.
urlopen=build_opener(ProxyHandler({})).open


class SnapshotTests(unittest.TestCase):
    def test_satellite_support_and_metrics(self):
        d=json.loads((ROOT/'data/calcatreu/satellite.json').read_text())
        count=d['width']*d['height']
        mask=base64.b64decode(d['commonMask'])
        arrays={k:struct.unpack('<'+'h'*count,base64.b64decode(v)) for k,v in d['arrays'].items()}
        self.assertEqual(len(mask),count)
        self.assertEqual(sum(mask),d['commonCells'])
        self.assertEqual([s['year'] for s in d['scenes']],list(range(2022,2027)))
        baseline=arrays['ndvi2022']
        baseline_veg=[i for i in range(count) if mask[i] and baseline[i]>=2000]
        for scene,metric in zip(d['scenes'],d['summary']):
            year=scene['year']; values=arrays[f'ndvi{year}']
            self.assertTrue(scene['date'].startswith(str(year)))
            self.assertTrue(scene['image'].startswith('data:image/jpeg;base64,'))
            self.assertTrue(all(values[i]!=-32768 for i in range(count) if mask[i]))
            self.assertEqual(metric['baselineVegetationHa'],len(baseline_veg)*d['cellAreaHa'])
            # Quantization can only change a threshold decision very near its boundary.
            retained=sum(values[i]>=2000 for i in baseline_veg)*4
            decline=sum(values[i]-baseline[i]<-1000 for i in baseline_veg)*4
            self.assertEqual(retained,metric['retainedHa'])
            self.assertEqual(decline,metric['declineHa'])
        self.assertEqual(d['summary'][0]['retainedPercent'],100)
        self.assertEqual(d['summary'][0]['declineHa'],0)

    def test_evidence_links_and_share_terms(self):
        d=json.loads((ROOT/'data/calcatreu/evidence.json').read_text())
        ids={n['id'] for n in d['entities']}
        for edge in d['relationships']:
            self.assertIn(edge['from'],ids);self.assertIn(edge['to'],ids)
        for event in d['events']:
            self.assertEqual(int(event['date'][:4]),event['year'])
            self.assertTrue(safe_url(event['url']))
        for stage in d['distributionStages']:
            self.assertEqual(stage['brm']+stage['pgl'],100)

    def test_news_deduplication_and_dates(self):
        results=[{'url':'https://example.com/calcatreu?tracking=1','title':'Calcatreu','content':'Evidence'},
                 {'url':'https://example.com/calcatreu?tracking=2','title':'Duplicate'},
                 {'url':'javascript:alert(1)','title':'Invalid'},
                 {'url':'https://example.com/new','title':'New','published_date':'2026-09-08T12:00:00Z'}]
        out=normalize_results([('Project',{'results':results})],'2026-09-25T12:00:00Z')
        self.assertEqual(len(out),2)
        self.assertIsNone(out[0]['publishedDate'])
        self.assertIsNone(out[0]['eventDate'])
        self.assertEqual(out[1]['publishedDate'],'2026-09-08')
        self.assertIsNone(safe_url('https://name:secret@example.com'))


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=dashboard_server.ThreadingHTTPServer(('127.0.0.1',0),dashboard_server.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()

    def test_snapshot_and_page(self):
        # Full satellite data is validated above and by the static export tests.
        # Keep loopback transport tests small; verify routing and script escaping.
        snapshot={'satellite':{'scenes':[]},'news':{'text':'</script><script>unexpected()</script>'}}
        with patch.object(dashboard_server,'snapshot',return_value=snapshot):
            with urlopen(self.url+'/api/dashboard',timeout=10) as r:
                body=r.read();d=json.loads(body)
            self.assertEqual(d,snapshot)
            self.assertNotIn(b'tvly-',body)
            with urlopen(self.url,timeout=10) as r:
                html=r.read()
            self.assertNotIn(b'__BOOTSTRAP__',html)
            self.assertNotIn(b'</script><script>unexpected()',html)
            self.assertNotIn(b'tvly-',html)
            self.assertIn(b'/dashboard.js',html)

    def test_external_origin_and_unapproved_refresh_blocked(self):
        for request in [Request(self.url+'/api/dashboard',headers={'Host':'untrusted.example'}),
                        Request(self.url+'/api/dashboard',headers={'Origin':'https://untrusted.example'}),
                        Request(self.url+'/api/refresh-news',method='POST')]:
            with self.assertRaises(HTTPError) as e: urlopen(request)
            self.assertEqual(e.exception.code,403)
            e.exception.close()

    def test_source_files_are_not_served(self):
        with self.assertRaises(HTTPError) as e: urlopen(self.url+'/dashboard_server.py')
        self.assertEqual(e.exception.code,404)
        e.exception.close()


if __name__=='__main__': unittest.main()
