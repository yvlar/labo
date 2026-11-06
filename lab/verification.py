"""Vérification reproductible sans métriques de performance sur données synthétiques."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import timedelta
import json
from pathlib import Path
from .data import canonical,digest,dt
from .engine import Engine
from .live import StreamingSession
from .storage import Journal
from .research import verify_dataset,revision


def inputs(dataset,config,model=None,software_test=False):
    dataset=Path(dataset);manifest=json.loads((dataset/'manifest.json').read_text())
    bars=verify_dataset(dataset,manifest)
    if manifest['metadata']['synthetic'] and not software_test:
        raise ValueError('Données synthétiques : --software-test obligatoire; aucune performance publiée')
    if not manifest['metadata']['synthetic'] and not manifest['metadata']['verified']:
        raise ValueError('Métadonnées de marché non vérifiées')
    cfg=json.loads(Path(config).read_text())
    if model:
        selected=[m for m in cfg['models'] if m['id']==model]
        if not selected:raise ValueError('Modèle absent de la configuration : '+model)
        cfg['models']=selected
    return bars,manifest,cfg


def objects(engine):
    return {str(tf):{'pivots':[asdict(p) for p in s.pivots], 'zones':[asdict(z) for z in s.zones],
                     'fvgs':deepcopy(s.fvgs),'trend':s.trend} for tf,s in engine.structures.items()}


def verify(root,dataset,config,output,model=None,software_test=False):
    bars,manifest,cfg=inputs(dataset,config,model,software_test)
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    indices=sorted({max(1,len(bars)//4),max(1,len(bars)//2),max(1,len(bars)*3//4),len(bars)})
    e=Engine(cfg,manifest['metadata']);states={}
    for n,b in enumerate(bars,1):
        e.push(b)
        if n in indices:states[n]=canonical({'snapshot':e.snapshot(),'objects':objects(e)})
    prefix=[]
    for n in indices:
        cut=Engine(cfg,manifest['metadata'])
        for b in bars[:n]:cut.push(b)
        known=canonical({'snapshot':cut.snapshot(),'objects':objects(cut)})==states[n]
        altered=Engine(cfg,manifest['metadata'])
        for i,b in enumerate(bars):
            if i>=n:b=replace(b,**{k:getattr(b,k)+1000 for k in ('open','high','low','close','ask_open','ask_high','ask_low','ask_close')})
            altered.push(b)
        causal=canonical(cut.events)==canonical([x for x in altered.events if x['available_at']<=bars[n-1].end])
        prefix.append({'until':bars[n-1].end,'known_objects_identical':known,'future_mutation_identical':causal})
    identity={'purpose':'REJEU EN FLUX, horloge virtuelle; aucune réception actuelle',
              'config':cfg,'manifest_hash':manifest['hash'],'revision':revision(root)}
    journal=Journal(out/'stream.sqlite',identity)
    stream=StreamingSession(cfg,manifest['metadata'],journal)
    restart_ok=True;duplicates_ok=True
    for i,b in enumerate(bars):
        stream.ingest(canonical(b.record()),b.end+timedelta(seconds=1))
        if i==len(bars)//2:
            state=canonical(stream.engine.snapshot());journal.close()
            journal=Journal(out/'stream.sqlite',identity)
            stream=StreamingSession(cfg,manifest['metadata'],journal)
            restart_ok=state==canonical(stream.engine.snapshot())
        if i%31==0:
            size=len(stream.engine.events)
            changed=stream.ingest(canonical(b.record()),b.end+timedelta(seconds=1))
            duplicates_ok &= not changed and len(stream.engine.events)==size
    parity=canonical(e.events)==canonical(stream.engine.events) and canonical(e.snapshot())==canonical(stream.engine.snapshot())
    stream_hash=stream.data_hash;journal.close()
    report={'purpose':'VÉRIFICATION LOGICIELLE, AUCUNE MESURE DE RENTABILITÉ','synthetic':manifest['metadata']['synthetic'],
            'revision':revision(root),'version':cfg['version'],'parameters':cfg,'config_hash':digest(cfg),
            'instrument':manifest['metadata'],'data_hash':manifest['hash'],'period':manifest['period'],
            'prefix_checks':prefix,'historical_stream_parity':parity,'restart_identical':restart_ok,'duplicates_idempotent':duplicates_ok,
            'stream_clock':'virtuelle : chaque M1 reçue à sa clôture +1s; même StreamingSession que live',
            'stream_data_hash':stream_hash,
            'current_market_feed_verified':False,'performance_metrics':None,
            'execution_assumptions':'bid/ask M1, limite pénétrée, stop prioritaire, une position dès ouverture de bougie'}
    report['passed']=parity and restart_ok and duplicates_ok and all(x['known_objects_identical'] and x['future_mutation_identical'] for x in prefix)
    (out/'verification.json').write_text(canonical(report))
    (out/'events.jsonl').write_text('\n'.join(canonical(x) for x in e.events)+'\n')
    (out/'transactions-software-test-only.json').write_text(canonical({'synthetic':manifest['metadata']['synthetic'],'purpose':report['purpose'],'transactions':e.broker.trades}))
    (out/'snapshot.json').write_text(canonical(e.snapshot()))
    return report


def export_decision(root,dataset,config,output,seq,model=None,software_test=False,following=120):
    bars,manifest,cfg=inputs(dataset,config,model,software_test)
    e=Engine(cfg,manifest['metadata'])
    for b in bars:e.push(b)
    event=next((x for x in e.events if x['seq']==seq),None)
    if not event:raise ValueError('Événement absent')
    decision=event['available_at'];prefix=Engine(cfg,manifest['metadata'])
    for b in bars:
        if b.end<=decision:prefix.push(b)
    order=event.get('order')
    if not order and event.get('order_id'):
        order=next((x['order'] for x in e.events if x['kind']=='ENTRY_PENDING' and x['order']['id']==event['order_id']),None)
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    try:import matplotlib
    except ImportError as e:raise ValueError('Export graphique : installer matplotlib ou l’option audit du projet') from e
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    from zoneinfo import ZoneInfo
    decision_index=sum(b.end<=decision for b in bars)
    for name,end in [('decision',decision_index),('after',min(len(bars),decision_index+following))]:
        shown=bars[max(0,decision_index-160):end]
        if not shown:raise ValueError('Aucune bougie disponible pour graphique')
        fig,ax=plt.subplots(figsize=(13,6))
        for b in shown:
            x=mdates.date2num(b.time);color='#17875c' if b.close>=b.open else '#b53c47'
            ax.vlines(x,b.low,b.high,color=color,linewidth=.8)
            ax.add_patch(Rectangle((x-.3/1440,min(b.open,b.close)),.6/1440,max(.002,abs(b.close-b.open)),color=color))
        refs=(order or {}).get('reasons',{})
        zone_ids={event.get('zone_id'),refs.get('htf_zone'),refs.get('entry_zone')}
        for s in prefix.structures.values():
            for z in s.zones:
                if z.id in zone_ids:
                    left=mdates.date2num(max(shown[0].time,z.available_at));right=mdates.date2num(shown[-1].end)
                    ax.add_patch(Rectangle((left,z.low),max(.05/1440,right-left),z.high-z.low,
                        color='#4399b4',alpha=.15,label=f'Zone {s.minutes}min dès {z.available_at.isoformat()}'))
        if order:
            for field,color in [('entry','#2463a2'),('stop','#b53c47'),('target','#17875c')]:
                ax.axhline(order[field],color=color,linestyle='--',label=field+' '+str(round(order[field],5)))
        ax.axvline(mdates.date2num(decision),color='#222',linestyle=':',label='Disponibilité décision')
        if name=='after' and order:
            for fill in e.events:
                if fill['kind']=='OPEN' and fill.get('order_id')==order['id'] and fill['available_at']<=shown[-1].end:
                    ax.scatter(mdates.date2num(fill.get('fill_time') or fill['available_at']),fill['fill'],marker='o',color='#2463a2',label='Exécution connue')
            for trade in e.broker.trades:
                if trade['id']==order['id']:
                    for leg in trade['exits']:
                        if leg['time']<=shown[-1].end:
                            ax.scatter(mdates.date2num(leg['time']),leg['price'],marker='x',color='#222',label='Sortie '+leg['reason'])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=ZoneInfo('America/Toronto')))
        meta=manifest['metadata'];tag='SYNTHÉTIQUE — TEST LOGICIEL, PAS PERFORMANCE' if meta['synthetic'] else 'DONNÉES DE MARCHÉ'
        method=next((m for m in cfg['models'] if m['id']==event['strategy']),None)
        pair=f"HTF {method['htf']}min / LTF {method['ltf']}min" if method else 'marché'
        trigger=refs.get('choch') or refs.get('model') or event['kind']
        ax.set_title(f"{tag}\nXAU/USD · {event['strategy']} · bougies M1 · {pair}\n{meta['provider']} / {meta.get('provider_symbol','fixture')} · {name} · déclencheur {trigger}",fontsize=11)
        ax.set_xlabel('America/Toronto · stockage UTC');ax.set_ylabel('USD / once troy')
        ax.legend(loc='best',fontsize=8);ax.grid(alpha=.15);fig.autofmt_xdate()
        fig.text(.01,.01,f"Données {manifest['hash'][:16]} · événement {seq} · connu à {decision.isoformat()} · stop/cible {'définis' if order else 'non définis'}",fontsize=8)
        fig.tight_layout(rect=(0,.03,1,1));fig.savefig(out/(name+'.png'),dpi=140);plt.close(fig)
    (out/'evidence.json').write_text(canonical({'revision':revision(root),'parameters':cfg,'manifest':manifest,
        'event':event,'known_objects_at_decision':objects(prefix),'decision_data_end':decision,'synthetic':manifest['metadata']['synthetic']}))
    return out
