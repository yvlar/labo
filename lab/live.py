"""Adaptateur fichier append-only pour un exporteur M1 courant; aucune connexion courtier."""
import json
import time
from datetime import datetime
from pathlib import Path
from .data import Bar, UTC, canonical, digest
from .engine import Engine
from .storage import Journal
from .research import revision

def probe(feed,seconds,output):
    """Bounded read-only connection check, even before an instrument is configured."""
    if not 0<seconds<=60:raise ValueError('Sonde bornée à 60 secondes maximum')
    start=datetime.now(UTC);deadline=time.monotonic()+seconds;seen=False
    while time.monotonic()<deadline:
        seen=seen or (Path(feed).is_file() and Path(feed).stat().st_size>0)
        time.sleep(min(.25,max(0,deadline-time.monotonic())))
    result={'mode':'CONTRÔLE DE CONNEXION SANS EXÉCUTION','started_at':start,
            'stopped_at':datetime.now(UTC),'duration_seconds':seconds,'feed':str(Path(feed).resolve()),
            'feed_present':seen,'status':'STOPPED','observation':'fichier présent, contenu non validé' if seen else 'WAITING : aucun flux reçu',
            'market_data_verified':False,'orders':0,'permanent_process':False}
    Path(output).write_text(canonical(result));return result

def run_live(root,config,metadata,feed,experiment,seconds=10,max_age=90):
    if seconds<=0 or max_age<=0:raise ValueError('Durée et fraîcheur doivent être positives')
    root=Path(root);cfg=json.loads(Path(config).read_text());spec=json.loads(Path(metadata).read_text())
    if not spec.get('verified') or spec.get('synthetic') or spec.get('price_kind')!='bid_ask':
        raise ValueError('Flux direct : métadonnées vérifiées et données de marché bid/ask requises')
    path=root/'runs'/experiment;path.mkdir(parents=True,exist_ok=True)
    identity={'config':cfg,'instrument':spec,'revision':revision(root),'mode':'SIMULATION DIRECTE',
              'feed':str(Path(feed).resolve()),'max_age_seconds':max_age}
    engine=Engine(cfg,spec);journal=Journal(path/'journal.sqlite',identity)
    journal.restore(engine)
    (path/'identity.json').write_text(canonical(identity))
    journal.health('STARTING','Simulateur interne; aucune route vers un compte externe')
    deadline=time.monotonic()+seconds;offset=0;halted=False;status='WAITING';last_status=None
    try:
        while time.monotonic()<deadline:
            file=Path(feed)
            if file.exists():
                if file.stat().st_size<offset:
                    halted=True;status='HALTED';journal.health(status,'Flux tronqué : redémarrage de l’exporteur à examiner')
                with file.open() as f:
                    f.seek(offset)
                    while True:
                        line=f.readline()
                        if not line:break
                        if not line.endswith('\n'):break  # partially written record; retry next poll
                        offset=f.tell()
                        try:
                            b=Bar.parse(json.loads(line));now=datetime.now(UTC)
                            if b.end>now:
                                raise ValueError('Bougie non clôturée/future')
                            fresh=(now-b.end).total_seconds()<=max_age
                            journal.append(engine,b,fresh and not halted)
                            status='HALTED' if halted else ('HEALTHY' if fresh else 'STALE')
                        except (ValueError,KeyError,TypeError) as e:
                            halted=True;status='HALTED';journal.health(status,str(e))
            now=datetime.now(UTC)
            if not engine.last:status='WAITING' if not halted else 'HALTED'
            elif (now-engine.last.end).total_seconds()>max_age and not halted:status='STALE'
            if status!=last_status:
                journal.health(status,'Nouvelles entrées autorisées' if status=='HEALTHY' else
                               'Entrées arrêtées; positions conservées, protections simulées au prochain prix reçu')
                last_status=status
            (path/'snapshot.json').write_text(canonical(engine.snapshot()|{'mode':'SIMULATION DIRECTE',
                'health':status,'observed_at':now,'freshness_seconds':(now-engine.last.end).total_seconds() if engine.last else None}))
            time.sleep(min(.25,max(0,deadline-time.monotonic())))
    finally:
        journal.health('STOPPED','Essai borné terminé; positions et ordres conservés; aucune surveillance après arrêt')
        snapshot=engine.snapshot()|{'mode':'SIMULATION DIRECTE','health':'STOPPED','last_health':status,
                                    'observed_at':datetime.now(UTC)}
        (path/'snapshot.json').write_text(canonical(snapshot))
        journal.close()
    return snapshot
