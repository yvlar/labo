"""Adaptateur fichier append-only pour un exporteur M1 courant; aucune connexion courtier."""
import json
import time
import math
import hashlib
from datetime import datetime
from pathlib import Path
from .data import Bar, UTC, canonical, digest, validate_instrument
from .engine import Engine
from .storage import Journal
from .research import revision

class StreamingSession:
    """The actual ingestion path, shared by current simulation and explicitly virtual-clock replay."""
    def __init__(self,cfg,spec,journal,max_age=90):
        self.engine=Engine(cfg,spec);self.journal=journal;self.max_age=max_age
        journal.restore(self.engine)
        self.halted=journal.halted();self.status='HALTED' if self.halted else 'WAITING'
        self.data_hash=digest(spec)
        for b in self.engine.bars:self.data_hash=hashlib.sha256((self.data_hash+canonical(b.record())).encode()).hexdigest()

    def halt(self,reason):
        self.halted=True;self.status='HALTED';self.journal.latch_halt(reason)

    def ingest(self,payload,received_at):
        try:
            b=Bar.parse(json.loads(payload))
            if b.end>received_at:raise ValueError('Bougie non clôturée/future')
            fresh=(received_at-b.end).total_seconds()<=self.max_age
            changed=self.journal.append(self.engine,b,fresh and not self.halted)
            if changed:self.data_hash=hashlib.sha256((self.data_hash+canonical(b.record())).encode()).hexdigest()
            self.status='HALTED' if self.halted else ('HEALTHY' if fresh else 'STALE')
            return changed
        except (ValueError,KeyError,TypeError) as e:
            self.halt(str(e));return False

    def health_at(self,now):
        if self.halted:return 'HALTED'
        if not self.engine.last:return 'WAITING'
        return 'HEALTHY' if (now-self.engine.last.end).total_seconds()<=self.max_age else 'STALE'

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
    if not math.isfinite(seconds) or seconds<=0 or not math.isfinite(max_age) or not 0<max_age<=300:
        raise ValueError('Durée finie positive et fraîcheur entre 0 et 300 secondes requises; utiliser verify-engine pour le rejeu ancien')
    root=Path(root);cfg=json.loads(Path(config).read_text());spec=json.loads(Path(metadata).read_text())
    validate_instrument(spec)
    if not spec.get('verified') or spec.get('synthetic') or spec.get('price_kind')!='bid_ask':
        raise ValueError('Flux direct : métadonnées vérifiées et données de marché bid/ask requises')
    path=root/'runs'/experiment;path.mkdir(parents=True,exist_ok=True)
    identity={'config':cfg,'instrument':spec,'revision':revision(root),'mode':'SIMULATION DIRECTE',
              'feed':str(Path(feed).resolve()),'max_age_seconds':max_age}
    journal=Journal(path/'journal.sqlite',identity)
    session=StreamingSession(cfg,spec,journal,max_age);engine=session.engine
    (path/'identity.json').write_text(canonical(identity))
    journal.health('STARTING','Simulateur interne; aucune route vers un compte externe')
    deadline=time.monotonic()+seconds;offset=0;status=session.status;last_status=None
    try:
        while time.monotonic()<deadline:
            file=Path(feed)
            if file.exists():
                if file.stat().st_size<offset:
                    session.halt('Flux tronqué : redémarrage de l’exporteur à examiner')
                with file.open() as f:
                    f.seek(offset)
                    while True:
                        line=f.readline()
                        if not line:break
                        if not line.endswith('\n'):break  # partially written record; retry next poll
                        offset=f.tell()
                        session.ingest(line,datetime.now(UTC))
            now=datetime.now(UTC)
            status=session.health_at(now)
            if status!=last_status:
                journal.health(status,'Nouvelles entrées autorisées' if status=='HEALTHY' else
                               'Entrées arrêtées; positions conservées, protections simulées au prochain prix reçu')
                last_status=status
            (path/'snapshot.json').write_text(canonical(engine.snapshot()|{'mode':'SIMULATION DIRECTE',
                'health':status,'observed_at':now,'stream_data_hash':session.data_hash,
                'freshness_seconds':(now-engine.last.end).total_seconds() if engine.last else None}))
            time.sleep(min(.25,max(0,deadline-time.monotonic())))
    finally:
        journal.health('STOPPED','Essai borné terminé; positions et ordres conservés; aucune surveillance après arrêt')
        snapshot=engine.snapshot()|{'mode':'SIMULATION DIRECTE','health':'STOPPED','last_health':status,
                                    'observed_at':datetime.now(UTC),'stream_data_hash':session.data_hash}
        (path/'snapshot.json').write_text(canonical(snapshot))
        journal.close()
    return snapshot
