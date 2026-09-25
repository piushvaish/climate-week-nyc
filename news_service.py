"""Tavily retrieval with server-side secrets, bounded usage and durable snapshots."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data' / 'calcatreu'
CA = ROOT / 'data' / 'trusted-ca.pem'


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_url(value):
    if not isinstance(value,str):
        return None
    parts=urlsplit(value)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
        return None
    return urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))


def search(key, query, start_date='2022-01-01', include_answer=False):
    payload = {'query':query,'topic':'general','search_depth':'advanced','max_results':5,
               'start_date':start_date,'end_date':datetime.now(timezone.utc).date().isoformat(),
               'include_answer':'advanced' if include_answer else False,
               'include_raw_content':False,'include_usage':True}
    request = Request('https://api.tavily.com/search', data=json.dumps(payload).encode(), method='POST',
                      headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    context=ssl.create_default_context(cafile=str(CA)) if CA.exists() else ssl.create_default_context()
    try:
        with urlopen(request, context=context, timeout=75) as response:
            return json.load(response)
    except HTTPError as exc:
        # Never echo request headers, request objects or provider bodies containing secrets.
        raise RuntimeError(f'Tavily returned HTTP {exc.code}; last successful snapshot retained.') from None
    except (URLError,TimeoutError):
        raise RuntimeError('Tavily connection failed; last successful snapshot retained.') from None


def normalize_results(responses, retrieved_at):
    seen=set()
    stories=[]
    for category,payload in responses:
        for item in payload.get('results',[]):
            url=safe_url(item.get('url'))
            title=str(item.get('title') or '').strip()
            if not url or not title:
                continue
            identity=(urlsplit(url).netloc.lower(),urlsplit(url).path.rstrip('/'))
            if identity in seen:
                continue
            seen.add(identity)
            publication=item.get('published_date') or item.get('published_time')
            # Preserve provider dates, never convert URL fragments or retrieval dates into event dates.
            if publication:
                match=re.search(r'(?<!\d)20\d{2}-\d{2}-\d{2}(?!\d)',str(publication))
                publication=match.group(0) if match else None
                try:
                    if publication:
                        datetime.strptime(publication,'%Y-%m-%d')
                except ValueError:
                    publication=None
            stories.append({'id':f'tavily-{len(stories)+1}','title':title[:220], 'url':url,
                            'publisher':urlsplit(url).hostname.removeprefix('www.'),
                            'publishedDate':publication,'eventDate':None,'dateBasis':'publication' if publication else 'unknown',
                            'retrievedAt':retrieved_at,'category':category,
                            'excerpt':str(item.get('content') or '')[:650],
                            'sourceType':'company' if urlsplit(url).hostname in ('patagoniagold.com','www.patagoniagold.com') else 'web',
                            'retrievalProvider':'Tavily'})
    return stories


def refresh_news(key):
    if not key:
        raise RuntimeError('Tavily key not configured on the server.')
    queries=[('Project','Calcatreu Patagonia Gold 2026 production first gold leaching March September',True),
             ('Environment','Calcatreu Río Negro impacto ambiental vegetación agua minería 2024 2025 2026',False),
             ('Money','Patagonia Gold Calcatreu Black River Mine financing 40 million May 30 2025 ownership',False)]
    responses=[]
    for category,query,answer in queries:
        responses.append((category,search(key,query,include_answer=answer)))
    timestamp=now()
    stories=normalize_results(responses,timestamp)
    if not stories:
        raise RuntimeError('Tavily returned no usable sources; previous snapshot retained.')
    raw_answer=responses[0][1].get('answer')
    brief=str(raw_answer or '')[:3500]
    doc={'status':'ok','provider':'Tavily','retrievedAt':timestamp,'stories':stories,
         'brief':{'text':brief,'generatedAt':timestamp,'provider':'Tavily AI answer',
                  'sourceUrls':[safe_url(r.get('url')) for r in responses[0][1].get('results',[]) if safe_url(r.get('url'))]},
         'queryCount':len(queries),'usage':[p.get('usage') for _,p in responses]}
    OUT.mkdir(parents=True,exist_ok=True)
    temp=OUT/'news.tmp'
    temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(OUT/'news.json')
    return doc
