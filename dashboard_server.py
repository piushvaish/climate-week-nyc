"""Local dashboard. Tavily secret stays in server memory, never the browser.

Run with TAVILY_API_KEY in the environment or --ask-tavily-key (hidden prompt).
News refreshes at most hourly while running. Satellite/MCP data stay explicit
snapshots; they are never represented as automatically refreshed here.
"""
import argparse
from datetime import datetime,timezone
import getpass
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from news_service import refresh_news,now

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'calcatreu'
state={'refreshing':False,'lastError':None,'lastAttempt':None,'tavilyConfigured':False}
lock=threading.Lock()
secret=None


def read_json(name,default):
    path=DATA/name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def snapshot():
    return {'satellite':read_json('satellite.json',None),
            'evidence':read_json('evidence.json',{'events':[],'entities':[],'relationships':[]}),
            'news':read_json('news.json',{'status':'pending','stories':[]}),
            'sayari':read_json('sayari.json',{'status':'pending','message':'Account authorization pending','entities':[],'relationships':[]}),
            'service':dict(state),'servedAt':now()}


def refresh(force=False):
    with lock:
        if state['refreshing']:
            return False
        if state['lastAttempt'] and time.time()-state['lastAttempt'] < (60 if force else 3600):
            return False
        state.update(refreshing=True,lastAttempt=time.time(),lastError=None)
    try:
        refresh_news(secret)
    except Exception as exc:
        # news_service emits sanitized errors only. Never log the credential.
        with lock:
            state['lastError']=str(exc) if isinstance(exc,RuntimeError) else 'Refresh failed; saved evidence remains available.'
    finally:
        with lock:
            state['refreshing']=False
    return True


def worker():
    while True:
        if secret:
            refresh()
        time.sleep(30)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):
        pass

    def send(self,code,payload,content_type='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def local_request(self):
        # Refuse DNS-rebinding and browser-origin requests from outside this app.
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in allowed:
            return False
        origin=self.headers.get('Origin')
        return not origin or origin in {'http://'+host for host in allowed}

    def do_GET(self):
        if not self.local_request():
            return self.send(403,b'{"error":"Local access only"}')
        path=urlsplit(self.path).path
        if path=='/api/dashboard':
            return self.send(200,json.dumps(snapshot(),ensure_ascii=False).encode())
        if path in ('/','/index.html'):
            content=(ROOT/'dashboard'/'index.html').read_text(encoding='utf-8')
            content=content.replace('__BOOTSTRAP__',json.dumps(snapshot(),ensure_ascii=False).replace('</','<\\/'))
            return self.send(200,content.encode(),'text/html; charset=utf-8')
        static={'/dashboard.js':'application/javascript; charset=utf-8','/live.js':'application/javascript; charset=utf-8',
                '/dashboard.css':'text/css; charset=utf-8','/d3.min.js':'application/javascript; charset=utf-8'}
        if path in static:
            file=ROOT/'dashboard'/path[1:]
            if file.exists():
                return self.send(200,file.read_bytes(),static[path])
        self.send(404,b'{"error":"Not found"}')

    def do_POST(self):
        if not self.local_request() or self.headers.get('X-Dashboard-Request')!='refresh':
            return self.send(403,b'{"error":"Local access only"}')
        if urlsplit(self.path).path!='/api/refresh-news':
            return self.send(404,b'{"error":"Not found"}')
        if not secret:
            return self.send(503,b'{"error":"Tavily not configured"}')
        with lock:
            busy=state['refreshing'] or (state['lastAttempt'] and time.time()-state['lastAttempt']<60)
        if busy:
            return self.send(429,b'{"error":"Refresh already running or requested within the last minute"}')
        threading.Thread(target=refresh,kwargs={'force':True},daemon=True).start()
        self.send(202,b'{"status":"refreshing"}')


def main():
    global secret
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--ask-tavily-key',action='store_true')
    args=parser.parse_args()
    secret=os.environ.get('TAVILY_API_KEY')
    if args.ask_tavily_key:
        secret=getpass.getpass('Tavily key (hidden; held only in memory): ').strip()
    state['tavilyConfigured']=bool(secret)
    saved=read_json('news.json',{})
    if saved.get('retrievedAt'):
        try:
            state['lastAttempt']=datetime.fromisoformat(saved['retrievedAt']).timestamp()
        except (ValueError,TypeError):
            pass
    threading.Thread(target=worker,daemon=True).start()
    print(f'Dashboard listening on http://127.0.0.1:{args.port} | Tavily {"configured" if secret else "not configured"}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':
    main()
