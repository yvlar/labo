"""Préré enregistrement immuable et évaluation chronologique sans sélection sur le test."""
from __future__ import annotations
import json
import math
import random
import subprocess
from copy import deepcopy
from pathlib import Path
from statistics import mean
from .data import canonical, digest, dt, read_csv, validate_instrument
from .engine import Engine, validate_config

def evaluation_verdict(result,min_trades):
    ci=result['daily_bootstrap_expectancy_ci95']
    if result['trades']<min_trades or not ci:return 'non concluant'
    if ci[1]<=0:return 'échec'
    if ci[0]<=0:return 'non concluant'
    return 'à confirmer prospectivement'

def stress_bar(b,multiplier):
    """OHLC spread stress is an envelope approximation, never synchronized tick reconstruction."""
    from dataclasses import replace
    ask={name:getattr(b,name)+multiplier*(getattr(b,'ask_'+name)-getattr(b,name)) for name in ('open','high','low','close')}
    ask['high']=max(ask['high'],ask['open'],ask['close'])
    ask['low']=min(ask['low'],ask['open'],ask['close'])
    return replace(b,**{'ask_'+k:v for k,v in ask.items()})

def opportunity_metrics(events,trades,start,end):
    ev=[e for e in events if start<=e['available_at']<end]
    ids={e['opportunity_id'] for e in ev if e['kind']=='OPPORTUNITY'}
    orders={e['order']['id']:e['order'] for e in ev if e['kind']=='ENTRY_PENDING'}
    outcomes={e['order_id']:e['kind'] for e in events if e['available_at']<end and e.get('order_id') in orders
              and e['kind'] in {'OPEN','CLOSED','EXPIRED','ORDER_REFUSED','INVALIDATED'}}
    filled={e['order_id'] for e in events if e['available_at']<end and e['kind']=='OPEN' and e.get('order_id') in orders}
    cohort=[t for t in trades if start<=t['opened_at'] and t['closed_at']<end and t.get('closed_available_at',t['closed_at'])<=end and t.get('reasons',{}).get('opportunity_id') in ids]
    unresolved={o['reasons'].get('opportunity_id') for oid,o in orders.items() if outcomes.get(oid) not in {'CLOSED','EXPIRED','ORDER_REFUSED','INVALIDATED'}}
    return {'eligible_opportunities':len(ids),'submitted_signals':len(orders),'filled_orders':len(filled),
            'never_filled_observed':sum(outcomes.get(oid) in {'EXPIRED','ORDER_REFUSED','INVALIDATED'} and oid not in filled for oid in orders),
            'pending_or_open_at_boundary':len(unresolved),
            'closed_trades_in_opportunity_cohort':len(cohort),
            'net_r_per_eligible_opportunity_observed':sum(t['net_r'] for t in cohort)/len(ids) if ids else None,
            'net_cash_per_eligible_opportunity_observed':sum(t['net'] for t in cohort)/len(ids) if ids else None,
            'definition':'Zone HTF initialement confirmée et alignée, ou range OPR complet. Absence de signal/remplissage =0; positions/ordres encore ouverts censurés et comptés; pas une preuve si censurés.'}

def revision(root):
    p=subprocess.run(['git','rev-parse','HEAD'],cwd=root,text=True,capture_output=True)
    commit=p.stdout.strip() if p.returncode==0 else 'uncommitted'
    files={str(f.relative_to(root)):f.read_text() for f in sorted((Path(root)/'lab').glob('*.py'))}
    return {'commit':commit,'code_hash':digest(files)}

def metrics(trades,curve,capital,seed=17):
    rs=[t['net_r'] for t in trades];pnls=[t['net'] for t in trades]
    pos=sum(x for x in pnls if x>0);neg=-sum(x for x in pnls if x<0)
    peak=capital;dd=0;worst=streak=0;days={};by_session={};by_month={}
    by_gold_session={};by_gold_regime={};spread_ratios=[]
    recovery=None;underwater=None;longest=0
    from zoneinfo import ZoneInfo
    for t in trades:
        streak=streak+1 if t['net']<0 else 0;worst=max(worst,streak)
        day=t['closed_at'].date().isoformat();days.setdefault(day,[]).append(t['net_r'])
        hour=t['opened_at'].astimezone(ZoneInfo('America/New_York')).hour
        session='New York' if 9<=hour<16 else ('Londres' if 3<=hour<9 else 'Autres')
        by_session[session]=by_session.get(session,0)+t['net']
        month=day[:7];by_month[month]=by_month.get(month,0)+t['net']
        context=t.get('reasons',{}).get('gold_context') or {}
        if context:
            session=context['session_bucket'];regime=context['volatility_regime']
            for buckets,key in ((by_gold_session,session),(by_gold_regime,regime)):
                bucket=buckets.setdefault(key,{'trades':0,'net':0.})
                bucket['trades']+=1;bucket['net']+=t['net']
            if context['spread_to_atr'] is not None:spread_ratios.append(context['spread_to_atr'])
    for i,p in enumerate(curve):
        peak=max(peak,p['equity']);dd=max(dd,peak-p['equity'])
        if p['equity']<peak and underwater is None:underwater=i
        if p['equity']>=peak and underwater is not None:
            longest=max(longest,i-underwater);underwater=None
    if underwater is None:recovery=longest
    positive_days=[sum(v) for v in days.values() if sum(v)>0]
    ci=None
    # Daily clustered bootstrap, including days with no transactions. No IID-trade assumption.
    for p in curve:days.setdefault(p['time'].date().isoformat(),[])
    if len(days)>=10 and rs:
        blocks=list(days.values());rng=random.Random(seed);samples=[]
        for _ in range(1000):
            chosen=[v for _ in blocks for v in rng.choice(blocks)]
            if chosen:samples.append(mean(chosen))
        samples.sort()
        if samples:ci=[samples[int(.025*(len(samples)-1))],samples[int(.975*(len(samples)-1))]]
    return {'trades':len(rs),'expectancy_net_r':mean(rs) if rs else None,
        'profit_factor':pos/neg if neg else None,'profit_factor_note':'indéfini si aucune perte',
        'win_rate':sum(x>0 for x in pnls)/len(rs) if rs else None,
        'average_win':mean([x for x in pnls if x>0]) if pos else None,
        'average_loss':mean([x for x in pnls if x<0]) if neg else None,
        'net_pnl':sum(pnls),'closed_return':sum(pnls)/capital,'drawdown':dd,
        'recovery_bars':recovery,'unrecovered':underwater is not None,'longest_loss_streak':worst,
        'fees_closed':sum(t['fees'] for t in trades),
        'mae_r_mean':mean(t['mae'] for t in trades) if trades else None,
        'mfe_r_mean':mean(t['mfe'] for t in trades) if trades else None,
        'exposure':sum(p['exposed'] for p in curve)/len(curve) if curve else 0,
        'daily_bootstrap_expectancy_ci95':ci,'days':len(days),'by_session_net':by_session,
        'by_month_net':by_month,'largest_positive_day_share':max(positive_days)/sum(positive_days) if positive_days else None,
        'by_gold_session':by_gold_session,'by_gold_volatility_regime':by_gold_regime,
        'mean_spread_to_atr_at_decision':mean(spread_ratios) if spread_ratios else None,
        'sample_warning':'Échantillon descriptif, aucune preuve de robustesse et aucune annualisation'}

def preregister(root,config,dataset,splits,experiment):
    root=Path(root);cfg=json.loads(Path(config).read_text());validate_config(cfg)
    manifest=json.loads((Path(dataset)/'manifest.json').read_text())
    validate_instrument(manifest['metadata'])
    if manifest['metadata']['synthetic'] or not manifest['metadata']['verified']:
        raise ValueError('Recherche de performance interdite : données synthétiques ou métadonnées non vérifiées')
    split=json.loads(Path(splits).read_text())
    points=[dt(split[k]) for k in ['start','train_end','validation_end','end']]
    if not all(a<b for a,b in zip(points,points[1:])):
        raise ValueError('Découpage non chronologique')
    if points[0]<dt(manifest['period'][0]) or points[-1]>dt(manifest['period'][1]):
        raise ValueError('Découpage hors des données disponibles')
    r=cfg['research']
    count=len(cfg['models'])*3
    if r['budget']<count:
        raise ValueError('Budget insuffisant pour référence et stress préenregistrés')
    path=root/'runs'/experiment;path.mkdir(parents=True,exist_ok=False)
    frozen={'config':cfg,'manifest':manifest,'splits':split,'revision':revision(root),
            'dataset':str(Path(dataset).resolve()),'experiment':experiment,
            'primary_metric':'espérance nette en R sur positions closes, avec attrition aux frontières affichée',
            'failure':'borne haute CI95 <=0 : échec; CI contenant 0 ou échantillon <100 : non concluant',
            'candidates':'Aucun ajustement automatique. Référence + coûts x2 + coûts x3, mêmes règles.',
            'planned_experiments':count,'final_test_access':'consultable une seule fois par expérience',
            'command':f'python -m lab.cli evaluate --experiment {experiment}'}
    frozen['hash']=digest(frozen)
    (path/'preregistration.json').write_text(canonical(frozen))
    return path

def verify_dataset(dataset,manifest):
    validate_instrument(manifest['metadata'])
    bars=read_csv(Path(dataset)/'bars.csv')
    if digest({'bars':[b.record() for b in bars],'metadata':manifest['metadata']})!=manifest['hash']:
        raise ValueError('Empreinte normalisée invalide')
    return bars

def evaluate(root,experiment):
    root=Path(root);path=root/'runs'/experiment
    reg=json.loads((path/'preregistration.json').read_text())
    test=dict(reg);saved=test.pop('hash')
    if digest(test)!=saved:raise ValueError('Préenregistrement modifié')
    validate_instrument(reg['manifest']['metadata'])
    if reg['manifest']['metadata']['synthetic'] or not reg['manifest']['metadata']['verified']:
        raise ValueError('Rapport de performance interdit : données synthétiques ou non vérifiées')
    if revision(root)['code_hash']!=reg['revision']['code_hash']:
        raise ValueError('Code modifié depuis le préenregistrement')
    # Exclusive creation records even a failed attempt. Never silently restores an untouched holdout.
    with (path/'test-access.json').open('x') as f:
        f.write(canonical({'status':'test consulté; toute modification exige une nouvelle réserve', 'hash':saved}))
    bars=verify_dataset(reg['dataset'],reg['manifest']);cfg=reg['config'];split=reg['splits']
    bounds=[dt(split[k]) for k in ['start','train_end','validation_end','end']]
    windows=list(zip(['apprentissage','validation','test_final'],bounds,bounds[1:]))
    # Expanding walk-forward, with fixed parameters and non-overlapping validation/test windows.
    results=[];spec=reg['manifest']['metadata']
    for model in cfg['models']:
        for stress in [1,2,3]:
            c=deepcopy(cfg);c['models']=[model];c['risk']['slippage_ticks']*=stress
            ins=deepcopy(spec);ins['commission_per_unit']*=stress;ins['financing_per_unit_day']*=stress
            eng=Engine(c,ins);states={}
            for b in bars:
                if b.time>=bounds[-1]:break
                if stress!=1:b=stress_bar(b,stress)
                eng.push(b,allow_entries=b.time>=bounds[0])
                for boundary in bounds[1:]:
                    if b.end<=boundary:states[boundary]={'available_at':b.end,'equity':eng.broker.equity,'position':deepcopy(eng.broker.position)}
            for label,start,end in windows:
                trades=[t for t in eng.broker.trades if t['opened_at']>=start and t['closed_at']<end and t.get('closed_available_at',t['closed_at'])<=end]
                purged=[t for t in eng.broker.trades if t['opened_at']<end and t['closed_at']>=start and t not in trades]
                curve=[p for p in eng.broker.curve if start<p['time']<=end]
                before=[p for p in eng.broker.curve if p['time']<=start]
                initial=before[-1]['equity'] if before else c['risk']['capital']
                ev=[e for e in eng.events if start<=e['available_at']<end]
                counts={k:sum(e['kind']==k for e in ev) for k in ['ENTRY_PENDING','OPEN','EXPIRED','ORDER_REFUSED','AMBIGUOUS_BAR','GOLD_SIGNAL_REFUSED']}
                cohort={e['order']['id'] for e in ev if e['kind']=='ENTRY_PENDING'}
                fills={e['order_id'] for e in ev if e['kind']=='OPEN'}
                counts['fill_rate']=len(cohort & fills)/len(cohort) if cohort else None
                counts['not_filled_in_window']=len(cohort-fills)
                counts['boundary_fills']=len(fills-cohort)
                counts['signals_per_observed_day']=counts['ENTRY_PENDING']/max(1,len({p['time'].date() for p in curve}))
                m=metrics(trades,curve,initial,seed=c['research']['seed'])
                opportunities=opportunity_metrics(eng.events,eng.broker.trades,start,end)
                verdict=evaluation_verdict(m,c['research']['min_trades'])
                results.append({'model':model['id'],'version':model['version'],'policy':model['exit'],
                    'parameters':model,'cost_stress':stress,'period':[start,end],'window':label,
                    'metrics':m,'orders':counts,'opportunities':opportunities,'purged_boundary_trades':len(purged),'verdict':verdict,
                    'state_at_window_end':states.get(end),
                    'gold_profile':c['gold'],'effective_primitives':eng.effective_primitives,
                    'baseline':'cash USD 0% sans rémunération, exposition 0; cassure OPR simple via BASELINE-breakout si sélectionnée'})
            name=model['id']+f'-cost{stress}'
            (path/(name+'-events.jsonl')).write_text('\n'.join(canonical(e) for e in eng.events)+'\n')
            (path/(name+'-trades.json')).write_text(canonical(eng.broker.trades))
    report={'preregistration':reg,'results':results,'walk_forward':'fenêtres validation puis test, paramètres fixes; aucune optimisation',
            'limits':['La purge exclut les transactions chevauchantes des statistiques de trades, mais le capital et les limites de risque restent continus.',
                      'MAE/MFE des bougies entières sont des bornes OHLC; aucune précision intrabougie inventée.',
                      'Profil de volume et horaires S6 désactivés par défaut.']}
    (path/'report.json').write_text(canonical(report))
    lines=['# Rapport historique et hors échantillon','',f"Données : {reg['manifest']['hash']}",
           f"Commit : {reg['revision']['commit']} · code : {reg['revision']['code_hash']}",'',
           '| Modèle | Coûts | Fenêtre | Trades | Espérance R | Verdict |','|---|---:|---|---:|---:|---|']
    for r in results:
        lines.append(f"| {r['model']} | {r['cost_stress']} | {r['window']} | {r['metrics']['trades']} | {r['metrics']['expectancy_net_r']} | {r['verdict']} |")
    lines+=['','Reproduction : `'+reg['command']+'` (réexécuter dans une copie, conserver le témoin de consultation du test).',
            '', 'Paramètres, fournisseur, période, coûts, empreintes et limites détaillés dans report.json.']
    (path/'report.md').write_text('\n'.join(lines))
    return path/'report.md'
