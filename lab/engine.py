import math
from copy import deepcopy
from .data import canonical, digest, check, Resampler, validate_instrument
from .primitives import Structure
from .execution import Broker
from .strategies import Model
from .gold import GoldDesk, validate_profile

FAMILIES={'M1','M2','M3','M4A','M4B','M5A','M5B','M6A','M6B','M6C','BASELINE'}

def validate_config(cfg):
    if cfg.get('execution')!={'mode':'internal','account_type':'simulation','endpoint':None}:
        raise ValueError('Seul le simulateur interne est autorisé; comptes/endpoints externes refusés')
    if set(cfg)-{'version','execution','risk','primitives','models','research','gold'}:
        raise ValueError('Clés de configuration inconnues')
    validate_profile(cfg.get('gold'))
    r=cfg['risk']
    for k,v in r.items():
        if isinstance(v,(int,float)) and (not math.isfinite(v) or v<0):
            raise ValueError('Paramètre de risque invalide : '+k)
    if not 0<r['risk_per_trade']<=.0025 or not r['risk_per_trade']<=r['max_open_risk']<=.005:
        raise ValueError('Risque au-delà des limites du laboratoire')
    if not 0<r['daily_loss_limit']<=.01 or not 0<r['partial_fraction']<1 or r['capital']<=0:
        raise ValueError('Limite quotidienne / capital / sortie partielle invalide')
    p=cfg['primitives']
    if min(p['pivot_left'],p['pivot_right'])<1 or p['zone_ttl_minutes']<=0 or p['break_margin']<0:
        raise ValueError('Primitives invalides')
    if len({m['id'] for m in cfg['models']})!=len(cfg['models']):
        raise ValueError('Identifiants de stratégies dupliqués')
    for m in cfg['models']:
        if m['family'] not in FAMILIES or m['exit'] not in {'E1','E2','E3','E4','E5'}:
            raise ValueError('Modèle/politique inconnu')
        if m['htf']<=m['ltf'] or m['ltf']<1 or m['order_ttl_minutes']<=0:
            raise ValueError('Unités/expiration invalides')
        if m['family']=='M1' and (m['htf'],m['ltf']) not in {(60,5),(240,15)}:
            raise ValueError('Couple M1 préenregistré invalide')
        if m['family'].startswith('M5') and m['ltf']!=1:
            raise ValueError('M5 exige une exécution M1')
        if m['family']=='M5B' and m['stop_variant']=='retest':
            raise ValueError('M5B sans retest ne peut pas utiliser un stop de retest')
        if m['family'] in {'M4A','M4B','M5A','M5B'} and (m['window_minutes'] not in {80,90} or m['stop_variant'] not in {'range','confirmation','retest'}):
            raise ValueError('Variante OPR invalide')

class Engine:
    def __init__(self,cfg,spec):
        validate_config(cfg)
        validate_instrument(spec)
        self.cfg,self.spec=deepcopy(cfg),deepcopy(spec)
        self.events=[];self.bars=[];self.last=None
        self.gold=GoldDesk(cfg['gold'],spec,self.emit)
        self.effective_primitives=deepcopy(cfg['primitives'])
        self.effective_primitives['break_margin']=cfg['gold']['break_margin_ticks']*spec['tick_size']
        self.effective_primitives['equal_tolerance']=cfg['gold']['equal_tolerance_ticks']*spec['tick_size']
        periods={1}|{m[k] for m in cfg['models'] for k in ('htf','ltf')}|{n for m in cfg['models'] for n in m.get('refinement_tfs',[])}
        self.resamplers={n:Resampler(n) for n in periods if n>1}
        self.structures={n:Structure(n,self.effective_primitives) for n in periods}
        self.broker=Broker(cfg['risk'],spec,self.emit,entry_guard=self.gold.fill_guard)
        # Stable lexicographic priority in portfolio mode; individual runs use one model.
        self.models=[Model(m,self) for m in sorted(cfg['models'],key=lambda m:m['id'])]

    def emit(self,kind,at,**payload):
        event={'seq':len(self.events)+1,'event_time':at,'available_at':at,'instrument':self.spec['symbol'],
               'strategy':'market','version':self.cfg['version'],'kind':kind,**payload}
        self.events.append(event)
        return event

    def push(self,b,allow_entries=True):
        check([b])
        if self.last and b.time<=self.last.time:
            if b==self.last:return []
            raise ValueError('Donnée tardive/correction : journal immuable; nouvel import requis')
        start=len(self.events)
        gap=self.last and b.time!=self.last.end
        if gap:
            self.gold.gap()
            self.broker.cancel(b.end,'Trou de données : nouvelle confirmation requise')
            for m in self.models:
                m.context=None;m.phase=None
            for s in self.structures.values():
                s.bars=[];s.pending_sweeps={}
            self.emit('DATA_GAP',b.end,start=self.last.end,end=b.time,
                      reason='Entrées suspendues sur cette bougie; stops existants gérés au prochain prix')
        # Cancel only on invalidations already known before this bar, without using its future HTF close.
        invalid={z.id for s in self.structures.values() for z in s.zones if z.invalid}
        active=[]
        for o in self.broker.orders:
            if any(o.reasons.get(k) in invalid for k in ('htf_zone','entry_zone')):
                self.emit('INVALIDATED',b.end,strategy=o.strategy,order_id=o.id,reason='Zone de l’ordre invalidée avant exécution')
            else:active.append(o)
        self.broker.orders=active
        self.broker.on_bar(b,allow_entries and not gap)
        self.gold.update(b)
        self.bars.append(b)
        events=[]
        for n in sorted(self.structures,reverse=True):
            candle=b if n==1 else self.resamplers[n].push(b)
            if candle:
                new=self.structures[n].push(candle)
                for e in new:
                    payload={k:v for k,v in e.items() if k not in ('kind','event_time')}
                    self.emit(e['kind'],e['event_time'],**payload)
                events.extend(new)
        if allow_entries and not gap:
            for model in self.models:
                model.on_bar(b,events)
        else:
            self.emit('ENTRY_HALTED',b.end,reason='Données périmées ou discontinues')
        self.last=b
        return self.events[start:]

    def snapshot(self):
        return {'version':self.cfg['version'],'config_hash':digest(self.cfg),
                'instrument':self.spec,'last_bar':self.last.record() if self.last else None,
                'cash':self.broker.cash,'equity':self.broker.equity,'drawdown':self.broker.drawdown,
                'open_position':self.broker.position,'orders':self.broker.orders,
                'trades':self.broker.trades,'ambiguous_bars':self.broker.ambiguous,'fees':self.broker.fees,
                'gold':self.gold.snapshot(),'effective_primitives':self.effective_primitives}
