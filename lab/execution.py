"""Simulateur interne exclusivement. Aucune dépendance de courtage."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import timedelta
from math import floor, ceil
from .data import validate_instrument
from copy import deepcopy

@dataclass
class Intent:
    id: str
    strategy: str
    direction: int
    kind: str
    entry: float
    stop: float
    target: float
    decision_at: object
    expires: object
    policy: str
    reasons: dict

def rounded(price,tick,up):
    return (ceil(price/tick-1e-9) if up else floor(price/tick+1e-9))*tick

class Broker:
    def __init__(self,cfg,instrument,emit,entry_guard=None):
        validate_instrument(instrument)
        self.cfg,self.spec,self.emit=deepcopy(cfg),deepcopy(instrument),emit
        self.entry_guard=entry_guard
        self.cash=cfg['capital'];self.position=None;self.orders=[];self.trades=[]
        self.equity=self.cash;self.peak=self.cash;self.drawdown=0
        self.day=None;self.day_equity=self.cash;self.daily_locked=False
        self.ambiguous=0;self.fees=0;self.curve=[]

    def submit(self,o):
        key=lambda x:(x.direction,x.reasons.get('htf_zone'),str(x.reasons.get('opr')),x.decision_at)
        if any(key(x)==key(o) for x in self.orders):
            self.emit('ORDER_REFUSED',o.decision_at,strategy=o.strategy,order_id=o.id,
                      reason='Occasion simultanée dupliquée dans le portefeuille')
            return
        self.orders.append(o)
        self.emit('ENTRY_PENDING',o.decision_at,strategy=o.strategy,order=asdict(o),reasons=o.reasons)

    def cancel(self,now,reason):
        for o in self.orders:
            self.emit('ORDER_REFUSED',now,strategy=o.strategy,order_id=o.id,reason=reason)
        self.orders=[]

    def _close(self,b,price,qty,reason,at=None):
        p=self.position;s=self.spec
        price=rounded(price,s['tick_size'],p['direction']==-1)
        gross=(price-p['entry'])*p['direction']*qty*s['point_value']
        cost=qty*s['commission_per_unit']
        self.cash+=gross-cost;self.fees+=cost
        p['net']+=gross-cost;p['fees']+=cost;p['remaining']-=qty
        leg={'time':at or b.end,'price':price,'qty':qty,'reason':reason,'gross':gross,'fee':cost}
        p['exits'].append(leg)
        self.emit('PARTIALLY_CLOSED' if p['remaining']>1e-8 else 'CLOSED',at or b.end,
                  available_at=b.end,strategy=p['strategy'],order_id=p['id'],exit=leg,net_to_date=p['net'])
        if p['remaining']<=1e-8:
            p['closed_at']=at or b.end;p['closed_available_at']=b.end;p['net_r']=p['net']/p['risk_initial']
            self.trades.append(p);self.position=None

    def _take_partial(self,b,price,at=None):
        p=self.position;s=self.spec
        q=floor(p['qty']*self.cfg['partial_fraction']/s['qty_step']+1e-9)*s['qty_step']
        if q>=s['min_qty'] and p['remaining']-q>=s['min_qty']:
            self._close(b,price,q,'PARTIAL_2R',at=at)
            p['stop']=p['entry'];p['partial_done']=True
            self.emit('BREAK_EVEN_ARMED',at or b.end,available_at=b.end,strategy=p['strategy'],stop=p['stop'],effective='bougie suivante')
        else:
            p['partial_done']=True
            self.emit('PARTIAL_REFUSED',b.end,strategy=p['strategy'],reason='Quantité minimale')

    def _manage(self,b):
        p=self.position
        if not p:
            return
        d=p['direction'];s=self.spec;slip=self.cfg['slippage_ticks']*s['tick_size']
        stop_for_bar=p['stop']
        partial=p['entry']+d*2*p['unit_risk']
        o,h,l,c=(b.open,b.high,b.low,b.close) if d==1 else (b.ask_open,b.ask_high,b.ask_low,b.ask_close)
        p['mae']=max(p['mae'],max(0,(p['entry']-l) if d==1 else (h-p['entry']))/p['unit_risk'])
        p['mfe']=max(p['mfe'],max(0,(h-p['entry']) if d==1 else (p['entry']-l))/p['unit_risk'])
        if b.time.date()!=p['last_funding_day']:
            days=(b.time.date()-p['last_funding_day']).days
            fee=p['remaining']*s['financing_per_unit_day']*days
            self.cash-=fee;p['net']-=fee;p['fees']+=fee;self.fees+=fee
            p['last_funding_day']=b.time.date()
            self.emit('FINANCING',b.time,available_at=b.end,strategy=p['strategy'],cost=fee,days=days)
        if p['entry_bar']<b.time or p['kind']=='market':
            if (o<=p['stop'] if d==1 else o>=p['stop']):
                self._close(b,o-d*slip,p['remaining'],'STOP',at=b.time);return
            if p['policy']=='E4' and not p['partial_done'] and (o>=partial if d==1 else o<=partial):
                self._take_partial(b,partial-d*slip,at=b.time)
            if (o>=p['target'] if d==1 else o<=p['target']):
                self._close(b,p['target']-d*slip,p['remaining'],'TARGET_OPEN',at=b.time);return
        stop_hit=l<=stop_for_bar if d==1 else h>=stop_for_bar
        target_hit=h>=p['target'] if d==1 else l<=p['target']
        partial_hit=(h>=partial if d==1 else l<=partial) and p['policy']=='E4' and not p['partial_done']
        if stop_hit and (target_hit or partial_hit):
            self.ambiguous+=1
            net=lambda price:(p['net']+(price-p['entry'])*d*p['remaining']*s['point_value']-p['remaining']*s['commission_per_unit'])/p['risk_initial']
            low_bound=net(stop_for_bar-d*slip);upper_bound=net(p['target']-d*slip) if target_hit else low_bound
            if partial_hit and not target_hit:
                q=floor(p['qty']*self.cfg['partial_fraction']/s['qty_step']+1e-9)*s['qty_step']
                if q>=s['min_qty'] and p['remaining']-q>=s['min_qty']:
                    gross=((partial-d*slip-p['entry'])*d*q+(stop_for_bar-d*slip-p['entry'])*d*(p['remaining']-q))*s['point_value']
                    upper_bound=(p['net']+gross-p['remaining']*s['commission_per_unit'])/p['risk_initial']
            self.emit('AMBIGUOUS_BAR',b.end,strategy=p['strategy'],order_id=p['id'],convention='stop prioritaire',
                      net_r_stop_target_bounds=[low_bound,upper_bound])
        if stop_hit:
            # Gaps are executed at the worse opening quote, then slippage.
            px=min(o,stop_for_bar)-slip if d==1 else max(o,stop_for_bar)+slip
            self._close(b,px,p['remaining'],'STOP');return
        # A touched limit may have filled after the high/low: no target profit on its entry bar.
        if p['entry_bar']==b.time and p['kind']=='limit':
            if target_hit or partial_hit:
                self.ambiguous+=1
                self.emit('AMBIGUOUS_BAR',b.end,strategy=p['strategy'],order_id=p['id'],convention='cible ignorée sur bougie entrée limite')
            return
        if partial_hit:
            self._take_partial(b,partial-d*slip)
        if self.position and target_hit:
            self._close(b,p['target']-d*slip,p['remaining'],'TARGET')

    def on_bar(self,b,allow_entries=True):
        s=self.spec
        occupied_at_open=self.position is not None
        if self.day!=b.time.date():
            self.day=b.time.date();self.day_equity=self.equity;self.daily_locked=False
        self._manage(b)
        # Mark existing exposure at the opening quote before admitting any order.
        mark=self.cash
        if self.position:
            p=self.position;quote=b.open if p['direction']==1 else b.ask_open
            mark+=(quote-p['entry'])*p['direction']*p['remaining']*s['point_value']
        if mark<=self.day_equity*(1-self.cfg['daily_loss_limit']):
            self.daily_locked=True
        pending=[]; filled_this_bar=False
        for o in self.orders:
            if b.time>=o.expires:
                self.emit('EXPIRED',b.end,strategy=o.strategy,order_id=o.id,reason='Validité terminée');continue
            eligible=o.decision_at+timedelta(seconds=self.cfg['latency_seconds'])
            if b.time<eligible:
                pending.append(o);continue
            reason=None
            if not allow_entries: reason='Incident ou données périmées'
            elif self.daily_locked: reason='Limite de perte quotidienne'
            elif occupied_at_open: reason='Position déjà ouverte au début de la bougie; sortie intrabougie non anticipable'
            elif self.position or filled_this_bar: reason='Une position simultanée / priorité déterministe'
            if reason:
                self.emit('ORDER_REFUSED',b.end,strategy=o.strategy,order_id=o.id,reason=reason);continue
            d=o.direction;slip=self.cfg['slippage_ticks']*s['tick_size']
            if o.kind=='market':
                px=(b.ask_open+slip) if d==1 else (b.open-slip)
            else:
                # Strict penetration rather than a mere touch. No liquidity/queue guarantee.
                hit=b.ask_low<=o.entry-s['tick_size'] if d==1 else b.high>=o.entry+s['tick_size']
                if not hit:
                    pending.append(o);continue
                px=o.entry  # no favorable gap improvement assumed
            px=rounded(px,s['tick_size'],d==1)
            stop=rounded(o.stop,s['tick_size'],d==-1)
            target=rounded(o.target,s['tick_size'],d==-1)
            unit=(px-stop)*d
            if unit<=0 or (target-px)*d<=0:
                self.emit('ORDER_REFUSED',b.end,strategy=o.strategy,order_id=o.id,reason='Gap / niveaux invalides');continue
            gold_check=self.entry_guard(b,o,px) if self.entry_guard else None
            if gold_check and not gold_check['allowed']:
                self.emit('ORDER_REFUSED',b.end,strategy=o.strategy,order_id=o.id,
                          reason=gold_check['reason'],gold_check=gold_check);continue
            budget=max(0,self.cash)*min(self.cfg['risk_per_trade'],self.cfg['max_open_risk'])
            unit_cost=unit*s['point_value']+2*s['commission_per_unit']+2*slip*s['point_value']
            qty=floor(budget/unit_cost/s['qty_step']+1e-9)*s['qty_step']
            margin=qty*px*s['point_value']*s['margin_rate']
            if qty<s['min_qty'] or margin>self.cash:
                self.emit('ORDER_REFUSED',b.end,strategy=o.strategy,order_id=o.id,reason='Taille minimale ou marge');continue
            fee=qty*s['commission_per_unit'];self.cash-=fee;self.fees+=fee
            self.position={'id':o.id,'strategy':o.strategy,'direction':d,'kind':o.kind,'entry':px,
                'stop':stop,'initial_stop':stop,'target':target,'qty':qty,'remaining':qty,
                'unit_risk':unit,'risk_initial':unit*qty*s['point_value'],'net':-fee,'fees':fee,
                'opened_at':b.time if o.kind=='market' else b.end,'entry_bar':b.time,
                'policy':o.policy,'partial_done':False,'exits':[],'mae':0.,'mfe':0.,
                'last_funding_day':b.time.date(),'reasons':o.reasons,'gold_fill_check':gold_check}
            filled_this_bar=True
            self.emit('OPEN',b.end,strategy=o.strategy,order_id=o.id,fill=px,qty=qty,
                      fill_time=b.time if o.kind=='market' else None,risk=self.position['risk_initial'],fee=fee)
            self._manage(b)
        self.orders=pending
        self.equity=self.cash
        if self.position:
            p=self.position;quote=b.close if p['direction']==1 else b.ask_close
            self.equity+=(quote-p['entry'])*p['direction']*p['remaining']*s['point_value']
        self.peak=max(self.peak,self.equity);self.drawdown=max(self.drawdown,self.peak-self.equity)
        if self.equity<=self.day_equity*(1-self.cfg['daily_loss_limit']):
            self.daily_locked=True
        self.curve.append({'time':b.end,'equity':self.equity,'cash':self.cash,
                           'exposed':self.position is not None,'daily_locked':self.daily_locked})
