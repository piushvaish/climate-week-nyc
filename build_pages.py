"""Build an allowlisted, credential-free static dashboard for GitHub Pages."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'calcatreu'


def make_snapshot(news_refresh_configured=False):
    read=lambda name:json.loads((DATA/name).read_text(encoding='utf-8'))
    return {
        'satellite':read('satellite.json'),
        'evidence':read('evidence.json'),
        'news':read('news.json'),
        # Sayari is not yet authenticated. Never implicitly publish a future private export.
        'sayari':{'status':'pending','message':'Account authorization pending','entities':[],'relationships':[]},
        'service':{'mode':'static','newsRefreshConfigured':bool(news_refresh_configured),
                   'tavilyConfigured':False,'refreshing':False,'lastError':None},
        'servedAt':datetime.now(timezone.utc).isoformat()
    }


def build(output,news_refresh_configured=False):
    output=Path(output).resolve()
    # Build only a dedicated directory; never overwrite source files or a repository root.
    if output==ROOT or output==ROOT/'dashboard' or output==DATA:
        raise ValueError('Choose a dedicated output directory')
    output.mkdir(parents=True,exist_ok=True)
    allowed={'index.html','dashboard.css','dashboard.js','pages.js','snapshot.json','.nojekyll'}
    existing={p.name for p in output.iterdir()}
    if existing-allowed:
        raise ValueError('Output contains unexpected files; use an empty build directory')
    snapshot=json.dumps(make_snapshot(news_refresh_configured),ensure_ascii=False,separators=(',',':'))
    if re.search(r'tvly-(?:dev|prod)-[A-Za-z0-9_-]{12,}',snapshot):
        raise ValueError('Credential pattern detected in export')
    html=(ROOT/'dashboard'/'index.html').read_text(encoding='utf-8')
    html=html.replace('__BOOTSTRAP__',snapshot.replace('</','<\\/'))
    html=html.replace('href="/dashboard.css"','href="./dashboard.css"')
    html=html.replace('src="/dashboard.js"','src="./dashboard.js"')
    html=html.replace('src="/live.js"','src="./pages.js"')
    icon="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%2326745c'/%3E%3Cpath d='M5 25L13 10L18 18L23 7L28 25Z' fill='%23f6f7f2'/%3E%3C/svg%3E"
    html=html.replace('</head>',f'  <meta name="description" content="Explore Calcatreu satellite vegetation observations from 2022–2026, sourced news and disclosed financing.">\n  <link rel="icon" type="image/svg+xml" href="{icon}">\n</head>')
    for name in ['dashboard.css','dashboard.js','pages.js']:
        shutil.copyfile(ROOT/'dashboard'/name,output/name)
    (output/'snapshot.json').write_text(snapshot,encoding='utf-8')
    (output/'index.html').write_text(html,encoding='utf-8')
    (output/'.nojekyll').write_text('',encoding='utf-8')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'site')
    parser.add_argument('--news-refresh-configured',action='store_true')
    args=parser.parse_args()
    print('Built',build(args.output,args.news_refresh_configured))
