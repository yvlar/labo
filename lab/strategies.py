from datetime import timedelta, time
from zoneinfo import ZoneInfo
from .execution import Intent
from .primitives import fibonacci

NY=ZoneInfo('America/New_York')

class Model:
    def __init__(self,cfg,engine):
        self.cfg,self.e=cfg,engine;self.name=cfg['id'];self.used=set();self.context=None
        self.day=None;self.range_bars=[];self.opr=None;self.phase=None;self.sent=False

    def note(self,b,reason,**details):
        self.e.emit('DECISION',b.end,strategy=self.name,reason=reason,**details)

    def order(self,b,d,entry,stop,target,kind,reasons):
        spec=self.e.spec;tick=spec['tick_size']
        if d*(entry-stop)<tick or d*(target-entry)<tick:
            self.note(b,'Stop/cible structurels indisponibles ou invalides');return False
        policy=self.cfg['exit']
        if policy in ('E2','E3'):
            target=entry+d*abs(entry-stop)*(2 if policy=='E2' else 3)
        if policy=='E5' and d*(target-entry)/abs(entry-stop)<2.5:
            self.note(b,'Ratio structurel inférieur à 2,5R');return False
        if policy=='E4' and d*(target-entry)/abs(entry-stop)<=2:
            self.note(b,'Cible structurelle avant le seuil partiel 2R');return False
        oid=f'{self.name}:{b.end.isoformat()}'
        expires=b.end+timedelta(minutes=self.cfg['order_ttl_minutes'])
        if self.opr:expires=min(expires,self.opr['start']+timedelta(minutes=self.cfg['window_minutes']))
        o=Intent(oid,self.name,d,kind,entry,stop,target,b.end,expires,policy,
                 reasons|{'rule_ids':self.cfg['rule_ids'],'version':self.cfg['version']})
        self.e.broker.submit(o);return True

    def target(self,d,entry):
        s=self.e.structures[self.cfg['htf']]
        levels=[p.price for p in s.pivots if p.side==d and not p.broken and d*(p.price-entry)>0]
        return min(levels) if d==1 and levels else (max(levels) if levels else entry)

    def on_bar(self,b,events):
        family=self.cfg['family']
        if family in ('M4A','M4B','M5A','M5B','BASELINE'):
            return self.opening(b,events)
        return self.supply(b,events)

    def supply(self,b,events):
        h=self.e.structures[self.cfg['htf']];l=self.e.structures[self.cfg['ltf']]
        family=self.cfg['family'];tick=self.e.spec['tick_size']
        if self.context:
            z=self.context['zone']
            if z.invalid or h.trend!=self.context['direction'] or (b.end-self.context['touch']).total_seconds()/60>self.cfg['setup_ttl_minutes']:
                self.e.emit('INVALIDATED',b.end,strategy=self.name,zone_id=z.id,reason='Zone invalide ou attente expirée')
                self.context=None
        if not self.context:
            zones=[z for z in h.zones if z.zone_kind==self.cfg.get('zone_kind','pivot') and not z.invalid and z.id not in self.used and z.available_at<=b.time
                   and z.direction==h.trend]
            if family=='M2':
                # Selection occurs once at parent activation, never after seeing which subzone held.
                parents=[z for z in h.zones if z.zone_kind==self.cfg.get('zone_kind','pivot') and not z.invalid and z.id not in self.used
                         and z.direction==h.trend and z.available_at==b.end]
                for z in parents:
                    self.used.add(z.id)
                    candidates=[z]
                    for tf in self.cfg.get('refinement_tfs',[self.cfg['ltf']]):
                        children=[q for q in self.e.structures[tf].zones if q.zone_kind==self.cfg.get('zone_kind','pivot')
                            and not q.invalid and q.direction==z.direction and q.available_at<=b.end
                            and any(p.low<=q.low<q.high<=p.high and p.origin<=q.origin for p in candidates)]
                        candidates=children
                    children=candidates
                    if not children:
                        self.note(b,'Aucune sous-zone confirmée dans la zone HTF',zone_id=z.id);continue
                    c=min(children,key=lambda c:(c.low,c.id)) if z.direction==1 else max(children,key=lambda c:(c.high,c.id))
                    entry=c.high+(b.ask_close-b.close) if z.direction==1 else c.low
                    stop=c.low-tick if z.direction==1 else c.high+tick+(b.ask_close-b.close)
                    self.order(b,z.direction,entry,stop,self.target(z.direction,entry),'limit',
                               {'htf_zone':z.id,'entry_zone':c.id,'selection':'extrême à activation HTF'})
                if not parents:self.note(b,'Attente activation HTF pour figer la sous-zone extrême')
                return
            touched=[z for z in zones if b.low<=z.high and b.high>=z.low]
            if not touched:
                self.note(b,'Structure indéterminée' if not h.trend else 'Attente retour zone HTF');return
            z=sorted(touched,key=lambda z:(z.available_at,z.id))[0]
            self.used.add(z.id);self.context={'zone':z,'touch':b.end,'direction':z.direction}
            self.e.emit('ZONE_TOUCHED',b.end,strategy=self.name,zone_id=z.id,
                        features={'contacts':z.contacts,'formed_sweep':z.formed_sweep,'bos':z.bos,
                                  'penetration':z.penetration,'trend':h.trend,
                                  'internal_liquidity_count':sum(not p.broken and
                                    min(b.close,z.low)<=p.price<=max(b.close,z.high) for p in l.pivots),
                                  'nested_htf':True,'discount_premium':self.location(h,z),
                                  'flip':'non vérifié','volume_profile':'désactivé par défaut'})
            return
        c=self.context;d=c['direction'];z=c['zone']
        if family.startswith('M6'):
            return self.candles(b,events,c)
        changes=[x for x in events if x['tf']==self.cfg['ltf'] and x['kind']=='CHoCH' and x['direction']==d]
        if not changes or b.end<=c['touch']:
            self.note(b,'Attente CHoCH LTF postérieur au contact',zone_id=z.id);return
        swept=l.last_sweep is not None and l.last_sweep[0]>=c['touch'] and l.last_sweep[1]==d
        if self.cfg.get('require_sweep') and not swept:
            self.note(b,'Filtre sweep au retest non satisfait',zone_id=z.id);self.context=None;return
        current_zones=[q for q in l.zones if q.zone_kind==self.cfg.get('zone_kind','pivot') and q.direction==d and q.available_at==b.end and not q.invalid]
        fvg=any(f['available_at']==b.end and f['direction']==d for f in l.fvgs)
        if family=='M3':
            if fvg:
                self.note(b,'Branche OTE exclue : FVG présent');self.context=None;return
            # Freeze impulse anchors at CHoCH, using the latest confirmed opposite pivot.
            p=next((p for p in reversed(l.pivots) if p.side==-d and p.available_at<=b.end),None)
            end=b.high if d==1 else b.low
            if not p or (end-p.price)*d<=0:
                self.note(b,'Ancrage causal OTE absent');self.context=None;return
            entry=fibonacci(p.price,end,.702)
            if d==1:entry+=b.ask_close-b.close
            stop=p.price-d*tick+(b.ask_close-b.close if d==-1 else 0)
            reasons={'htf_zone':z.id,'choch':changes[0]['pivot_id'],'sweep_at_retest':swept,
                     'anchors':[p.price,end],'depth':.702,'no_fvg':True}
        else:
            if self.cfg.get('require_fvg') and not fvg:
                self.note(b,'Branche Supply/Demand avec FVG non satisfaite');self.context=None;return
            if not current_zones:
                self.note(b,'CHoCH sans nouvelle zone pivot validée');self.context=None;return
            q=current_zones[-1]
            entry=q.high+(b.ask_close-b.close) if d==1 else q.low
            stop=q.low-tick if d==1 else q.high+tick+(b.ask_close-b.close)
            reasons={'htf_zone':z.id,'entry_zone':q.id,'choch':changes[0]['pivot_id'],
                     'sweep_at_retest':swept,'fvg_confluence':fvg,'direction':'continuation HTF'}
        self.order(b,d,entry,stop,self.target(d,entry),'limit',reasons)
        self.context=None

    def location(self,h,z):
        hi=next((p.price for p in reversed(h.pivots) if p.side==1),None)
        lo=next((p.price for p in reversed(h.pivots) if p.side==-1),None)
        if hi is None or lo is None or hi<=lo:return 'indéterminé'
        return 'discount' if (z.low+z.high)/2<(lo+hi)/2 else 'premium'

    def opening(self,b,events):
        local=b.time.astimezone(NY);family=self.cfg['family'];n=15 if family.startswith('M4') else 5
        if self.day!=local.date():
            self.day=local.date();self.range_bars=[];self.opr=None;self.phase=None;self.sent=False
        start=local.replace(hour=9,minute=30,second=0,microsecond=0)
        elapsed=(local-start).total_seconds()/60
        if 0<=elapsed<n:
            self.range_bars.append(b)
            if elapsed==n-1:
                bars=self.range_bars
                if len(bars)!=n or any(y.time!=x.end for x,y in zip(bars,bars[1:])):
                    self.note(b,'Range incomplet : séance désactivée');return
                self.opr={'high':max(x.high for x in bars),'low':min(x.low for x in bars),
                          'available_at':b.end,'start':bars[0].time}
                self.e.emit('OPR_READY',b.end,strategy=self.name,**self.opr)
            return
        if not self.opr or elapsed<n or self.sent:
            self.note(b,'Attente range OPR complet' if not self.opr else 'Occasion quotidienne déjà soumise');return
        if elapsed>=self.cfg['window_minutes']:
            self.note(b,'Fenêtre OPR terminée');return
        hi,lo=self.opr['high'],self.opr['low'];m=self.e.cfg['primitives']['break_margin']
        body=abs(b.close-b.open)/max(b.high-b.low,1e-12)
        bias=self.e.structures[self.cfg['htf']].trend
        if family=='BASELINE':
            d=1 if b.close>hi+m else (-1 if b.close<lo-m else 0)
            if d:self.open_order(b,d,lo,hi,{'model':'baseline cassure simple sans retest'},b)
            else:self.note(b,'Baseline : attente clôture hors range')
            return
        if family=='M5B':
            fs=[x for x in events if x['tf']==1 and x['kind']=='FVG']
            d=1 if b.close>hi+m else (-1 if b.close<lo-m else 0)
            recent=self.e.structures[1].bars[-3:]
            crossing=bool(recent and (recent[0].close<=hi if d==1 else recent[0].close>=lo))
            impulse=len(recent)==3 and abs(recent[1].close-recent[1].open)/max(recent[1].high-recent[1].low,1e-12)>=self.cfg['confirmation_body_min']
            if not d or not any(f['direction']==d for f in fs) or not crossing or not impulse:
                self.note(b,'Attente cassure avec FVG et déplacement confirmé');return
            if self.cfg.get('require_context') and bias!=d:
                self.note(b,'Contexte HTF non aligné');return
            return self.open_order(b,d,lo,hi,{'model':'FVG','opr':self.opr,'decision':'troisième clôture'},b)
        if family=='M4B':
            d=1 if b.low<lo-m and b.close>lo else (-1 if b.high>hi+m and b.close<hi else 0)
            if not d or body<self.cfg['confirmation_body_min'] or (b.close-b.open)*d<=0:
                self.note(b,'Attente sweep/rejet numérique de la borne M15');return
            if self.cfg.get('require_context') and bias!=d:
                self.note(b,'Contexte HTF non aligné');return
            entry=b.ask_close if d==1 else b.close
            stop=b.low-self.e.spec['tick_size'] if d==1 else b.ask_high+self.e.spec['tick_size']
            target=hi if d==1 else lo
            self.sent=self.order(b,d,entry,stop,target,'market',{'opr':self.opr,'model':'réintégration'})
            return
        if not self.phase:
            d=1 if b.close>hi+m else (-1 if b.close<lo-m else 0)
            if not d:
                self.note(b,'Attente clôture hors range');return
            if (family=='M4A' or self.cfg.get('require_context')) and bias!=d:
                self.note(b,'Contexte HTF indéterminé ou opposé');return
            self.phase={'direction':d,'break':b.end,'retest':None}
            self.e.emit('CONFIRMATION_PENDING',b.end,strategy=self.name,direction=d,opr=self.opr)
            return
        p=self.phase;d=p['direction'];level=hi if d==1 else lo
        if (b.end-p['break']).total_seconds()/60>self.cfg['setup_ttl_minutes']:
            self.phase=None;self.note(b,'Cassure expirée sans confirmation');return
        if (d==1 and b.close<lo) or (d==-1 and b.close>hi):
            self.phase=None;self.note(b,'Cassure invalidée par borne opposée');return
        if p['retest'] is None:
            if b.low<=level<=b.high and b.end>p['break']:
                p['retest']=b
                self.e.emit('ZONE_TOUCHED',b.end,strategy=self.name,level=level,role='retest OPR')
            else:self.note(b,'Attente retest après cassure')
            return
        ret=p['retest']
        confirmed=(b.close>max(level,ret.high)+m if d==1 else b.close<min(level,ret.low)-m)
        if not confirmed or (b.close-b.open)*d<=0 or body<self.cfg['confirmation_body_min']:
            self.note(b,'Attente clôture directionnelle au-delà de la bougie de retest');return
        self.open_order(b,d,lo,hi,{'model':'break/retest/confirmation','opr':self.opr,
                                  'break_at':p['break'],'retest_at':ret.end},ret)

    def open_order(self,b,d,lo,hi,reasons,ret):
        which=self.cfg['stop_variant'];tick=self.e.spec['tick_size']
        stop=(lo-tick if d==1 else hi+tick+(b.ask_close-b.close))
        if which=='confirmation':stop=b.low-tick if d==1 else b.ask_high+tick
        if which=='retest':stop=ret.low-tick if d==1 else ret.ask_high+tick
        entry=b.ask_close if d==1 else b.close
        target=entry+d*abs(entry-stop)*2
        if self.cfg['family']=='M4A':target=self.target(d,entry)
        reasons['stop_variant']=which
        self.sent=self.order(b,d,entry,stop,target,'market',reasons)

    def candles(self,b,events,c):
        # Experimental variants kept distinct; each follows HTF continuation context.
        d=c['direction'];family=self.cfg['family'];l=self.e.structures[self.cfg['ltf']]
        bars=l.bars
        if len(bars)<4 or bars[-1].end!=b.end:
            self.note(b,'Attente bougie LTF clôturée');return
        a,cur=bars[-2:];body=abs(cur.close-cur.open)/max(cur.high-cur.low,1e-12)
        sweep=l.last_sweep and l.last_sweep[0]>=c['touch'] and l.last_sweep[1]==d
        engulf=min(cur.open,cur.close)<=min(a.open,a.close) and max(cur.open,cur.close)>=max(a.open,a.close)
        if family=='M6A':valid=sweep and engulf and (cur.close-cur.open)*d>0 and body>=.6
        elif family=='M6B':
            wick=(min(a.open,a.close)-a.low if d==1 else a.high-max(a.open,a.close))/max(a.high-a.low,1e-12)
            valid=wick>=.5 and body>=.6 and (cur.close-cur.open)*d>0 and (cur.close>a.high if d==1 else cur.close<a.low)
        else:
            if any(x['kind']=='CHoCH' and x['tf']==self.cfg['ltf'] and x['direction']==d for x in events):
                c['choch_at']=b.end
            base=bars[-4:-1];hi=max(x.high for x in base);lo=min(x.low for x in base)
            if c.get('choch_at') and b.end>c['choch_at'] and not c.get('broken'):
                if all(abs(x.close-x.open)/max(x.high-x.low,1e-12)<=.5 for x in base) and (cur.close>hi if d==1 else cur.close<lo):
                    c['broken']={'level':hi if d==1 else lo,'time':b.end}
            broken=c.get('broken')
            valid=bool(broken and b.end>broken['time'] and cur.low<=broken['level']<=cur.high and
                       (cur.close-cur.open)*d>0 and body>=.6)
        if not valid:
            self.note(b,'Confirmation expérimentale absente',variant=family);return
        entry=b.ask_close if d==1 else b.close
        stop=min(a.low,cur.low)-self.e.spec['tick_size'] if d==1 else max(a.ask_high,cur.ask_high)+self.e.spec['tick_size']
        self.order(b,d,entry,stop,self.target(d,entry),'market',{'zone_id':c['zone'].id,'variant':family,'continuation':True})
        self.context=None
