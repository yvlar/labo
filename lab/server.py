"""Interface locale en lecture seule. Aucun endpoint de transaction ou de configuration."""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .data import canonical, dt, read_csv
from .engine import Engine

def serve(root,host='127.0.0.1',port=8080):
    root=Path(root).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,data,status=200,ctype='application/json; charset=utf-8'):
            if not isinstance(data,(str,bytes)):data=canonical(data)
            if isinstance(data,str):data=data.encode()
            self.send_response(status);self.send_header('Content-Type',ctype)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            u=urlparse(self.path);q=parse_qs(u.query)
            try:
                if u.path=='/api/catalog':
                    runs=[]
                    for p in sorted((root/'runs').iterdir()):
                        if p.is_dir():runs.append({'id':p.name,'live':(p/'journal.sqlite').exists(),
                            'report':(p/'report.json').exists(),'historical':(p/'history.json').exists()})
                    return self.reply({'runs':runs,'rules':json.loads((root/'docs/rules.json').read_text()),
                                       'models':json.loads((root/'configs/models.json').read_text()),
                                       'status':'Aucune mesure de marché disponible' if not runs else 'Laboratoire local'})
                if u.path.startswith('/api/'):
                    name=q.get('run',[''])[0]
                    if not name or Path(name).name!=name or name in ('.','..'):
                        raise ValueError('Expérience invalide')
                    run=(root/'runs'/name).resolve()
                    if run.parent!=root/'runs':raise ValueError('Chemin invalide')
                    if u.path=='/api/report':
                        return self.reply(json.loads((run/'report.json').read_text()))
                    if u.path=='/api/snapshot':
                        return self.reply(json.loads((run/'snapshot.json').read_text()))
                    if u.path=='/api/events':
                        with sqlite3.connect(f'file:{run}/journal.sqlite?mode=ro',uri=True) as db:
                            after=int(q.get('after',['0'])[0])
                            events=[json.loads(r[0]) for r in db.execute('SELECT payload FROM events WHERE seq>? ORDER BY seq LIMIT 500',(after,))]
                            health=[dict(zip(('time','status','reason'),r)) for r in db.execute('SELECT time,status,reason FROM health ORDER BY seq DESC LIMIT 10')]
                        return self.reply({'events':events,'health':health})
                    if u.path=='/api/replay':
                        # Server computes only the selected prefix. Future bars and objects never reach the client.
                        identity=json.loads((run/'history.json').read_text())
                        from .research import revision
                        if identity['revision']['code_hash']!=revision(root)['code_hash']:
                            raise ValueError('Code différent du rejeu enregistré : créer une nouvelle expérience')
                        bars=read_csv(Path(identity['dataset'])/'bars.csv')
                        n=max(0,min(int(q.get('n',['0'])[0]),len(bars)))
                        engine=Engine(identity['config'],identity['manifest']['metadata'])
                        for b in bars[:n]:engine.push(b)
                        from dataclasses import asdict
                        objects={str(k):{'pivots':[asdict(p) for p in s.pivots],
                            'zones':[asdict(z) for z in s.zones],'fvgs':s.fvgs,'trend':s.trend} for k,s in engine.structures.items()}
                        return self.reply({'snapshot':engine.snapshot(),'bars':[b.record() for b in bars[:n][-400:]],
                            'objects':objects,'events':engine.events[-300:],'total':len(bars),'n':n,
                            'mode':'HISTORIQUE','manifest':identity['manifest']})
                    return self.reply({'error':'Route inconnue'},404)
                file=root/'web'/({'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(u.path,'missing'))
                types={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}
                self.reply(file.read_bytes(),ctype=types.get(file.suffix,'text/plain'))
            except (ValueError,KeyError,FileNotFoundError,sqlite3.Error) as e:
                self.reply({'error':str(e)},400)
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Interface locale : http://{host}:{port} · Ctrl-C pour arrêter',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
