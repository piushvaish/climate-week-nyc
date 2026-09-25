import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import build_pages


class PagesTests(unittest.TestCase):
    def test_export_works_under_repository_subpath(self):
        with tempfile.TemporaryDirectory() as temp:
            output=build_pages.build(Path(temp)/'site')
            html=(output/'index.html').read_text(encoding='utf-8')
            self.assertNotIn('__BOOTSTRAP__',html)
            self.assertNotIn('/api/dashboard',html)
            self.assertNotIn('src="/',html)
            self.assertNotIn('href="/dashboard',html)
            self.assertNotIn('live.js',html)
            self.assertIn('src="./pages.js"',html)
            self.assertEqual({p.name for p in output.iterdir()},
                             {'index.html','snapshot.json','dashboard.css','dashboard.js','pages.js','.nojekyll'})
            payload=re.search(r'<script id="bootstrap" type="application/json">(.*?)</script>',html,re.S).group(1)
            embedded=json.loads(payload)
            self.assertEqual(embedded,json.loads((output/'snapshot.json').read_text(encoding='utf-8')))
            self.assertEqual(embedded['service']['mode'],'static')
            self.assertFalse(embedded['service']['newsRefreshConfigured'])
            self.assertEqual(embedded['sayari']['status'],'pending')

    def test_embedded_news_cannot_break_out_of_json_script(self):
        snapshot=build_pages.make_snapshot()
        snapshot['news']['brief']['text']='</script><script>invalid()</script>'
        with tempfile.TemporaryDirectory() as temp, patch.object(build_pages,'make_snapshot',return_value=snapshot):
            output=build_pages.build(Path(temp)/'site')
            html=(output/'index.html').read_text(encoding='utf-8')
            self.assertNotIn('</script><script>invalid()',html)
            self.assertIn('<\\/script>',html)

    def test_build_does_not_publish_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)
            (output/'private.txt').write_text('not a website asset')
            with self.assertRaises(ValueError):build_pages.build(output)
            self.assertTrue((output/'private.txt').exists())


if __name__=='__main__':unittest.main()
