from __future__ import annotations
from dataclasses import dataclass, asdict
from .data import Bar

@dataclass
class Pivot:
    id: str
    side: int  # +1 high, -1 low
    price: float
    pivot_time: object
    available_at: object
    label: str
    broken: bool = False
    swept: bool = False

@dataclass
class Zone:
    id: str
    direction: int
    low: float
    high: float
    origin: object
    available_at: object
    zone_kind: str
    pattern: str
    contacts: int = 0
    penetration: float = 0
    invalid: bool = False
    inside: bool = False
    formed_sweep: bool = False
    bos: bool = False

class Structure:
    def __init__(self, minutes, cfg):
        self.minutes, self.cfg = minutes, cfg
        self.bars, self.pivots, self.zones, self.fvgs = [], [], [], []
        self.trend = 0
        self.pending_sweeps = {}
        self.last_sweep = None
        self.sweeps=[]

    def push(self, b):
        events=[]
        self.bars.append(b)
        left,right=self.cfg['pivot_left'],self.cfg['pivot_right']
        def emit(kind, **payload):
            events.append({'kind':kind,'tf':self.minutes,'event_time':b.end,
                           'available_at':b.end,**payload})
        # Only previously active objects may be touched by this bar.
        for z in self.zones:
            if z.invalid:
                continue
            if (b.end-z.available_at).total_seconds()/60 > self.cfg['zone_ttl_minutes']:
                z.invalid=True; emit('ZONE_EXPIRED',zone_id=z.id); continue
            if (z.direction==1 and b.close<z.low) or (z.direction==-1 and b.close>z.high):
                z.invalid=True;emit('ZONE_INVALIDATED',zone_id=z.id);continue
            inside = b.low<=z.high and b.high>=z.low
            if inside and not z.inside:
                z.contacts+=1
                emit('ZONE_TOUCHED',zone_id=z.id,contacts=z.contacts)
            if inside:
                depth=(z.high-b.low)/(z.high-z.low) if z.direction==1 else (b.high-z.low)/(z.high-z.low)
                z.penetration=max(z.penetration,min(1,max(0,depth)))
            z.inside=inside
        for f in self.fvgs:
            if f['invalid']:
                continue
            depth=(f['high']-b.low)/(f['high']-f['low']) if f['direction']==1 else (b.high-f['low'])/(f['high']-f['low'])
            f['fill']=max(f['fill'],min(1,max(0,depth)))
            f['invalid']=(b.close<f['low'] if f['direction']==1 else b.close>f['high'])
        # Fixed confirmed pivot windows. Ties deliberately produce no pivot.
        if len(self.bars)>=left+right+1:
            idx=len(self.bars)-right-1
            c=self.bars[idx]
            win=self.bars[idx-left:idx]+self.bars[idx+1:idx+right+1]
            for side,price in [(1,c.high),(-1,c.low)]:
                if all(price>x.high if side==1 else price<x.low for x in win):
                    prev=next((p for p in reversed(self.pivots) if p.side==side),None)
                    label=('HH' if price>prev.price else 'LH') if side==1 and prev else (
                        ('HL' if price>prev.price else 'LL') if prev else ('H' if side==1 else 'L'))
                    p=Pivot(f'P{self.minutes}:{c.time.isoformat()}:{side}',side,price,c.time,b.end,label)
                    self.pivots.append(p)
                    emit('PIVOT',**asdict(p))
                    if prev and abs(price-prev.price)<=self.cfg['equal_tolerance']:
                        emit('EQUAL_LEVEL',pivot_id=p.id,other_id=prev.id,level=(price+prev.price)/2)
        margin=self.cfg['break_margin']
        breaks=[]
        for side in [1,-1]:
            p=next((p for p in reversed(self.pivots) if p.side==side),None)
            if not p or p.broken:
                continue
            crossed=b.close>p.price+margin if side==1 else b.close<p.price-margin
            if crossed:
                p.broken=True
                kind='CHoCH' if self.trend==-side else ('BOS' if self.trend==side else 'STRUCTURE_INIT')
                self.trend=side;breaks.append((kind,side))
                emit(kind,direction=side,pivot_id=p.id,level=p.price)
            # Sweep requires wick beyond, close back, within bounded bars; persistent break is rejected.
            wick=b.high>p.price+margin if side==1 else b.low<p.price-margin
            back=b.close<p.price if side==1 else b.close>p.price
            if wick and not p.swept:
                self.pending_sweeps.setdefault(p.id,(p,len(self.bars)))
        # A temporary close outside is not retroactively erased as a structure break.
        # Its later reintegration is a NEW event, available only on that later close.
        for pid,(p,started) in list(self.pending_sweeps.items()):
            back=b.close<p.price if p.side==1 else b.close>p.price
            if len(self.bars)-started>self.cfg['sweep_bars']:
                del self.pending_sweeps[pid]
            elif back:
                p.swept=True;self.last_sweep=(b.end,-p.side)
                self.sweeps.append({'available_at':b.end,'direction':-p.side,'pivot_id':p.id})
                emit('SWEEP',pivot_id=p.id,direction=-p.side,level=p.price)
                del self.pending_sweeps[pid]
        if len(self.bars)>=2:
            p=self.bars[-2]
            rng=max(p.high-p.low,1e-12)
            body=abs(p.close-p.open)/rng
            strength=abs(b.close-b.open)/max(b.high-b.low,1e-12)
            d=1 if b.close>p.high+margin else (-1 if b.close<p.low-margin else 0)
            if d and body<=self.cfg['base_body_max'] and strength>=self.cfg['impulse_body_min']:
                incoming=1 if p.close>=p.open else -1
                if len(self.bars)>=3:
                    incoming=1 if p.close>=self.bars[-3].close else -1
                pattern=('Rally' if incoming==1 else 'Drop')+'–Base–'+('Rally' if d==1 else 'Drop')
                if p.high>p.low:
                    z=Zone(f'Z{self.minutes}:{p.time.isoformat()}:{d}',d,p.low,p.high,p.time,b.end,
                           'pivot',pattern,formed_sweep=any(p.time<=s['available_at']<=b.end and s['direction']==d for s in self.sweeps),
                           bos=any(k=='BOS' and s==d for k,s in breaks))
                    self.zones.append(z);emit('ZONE_ACTIVE',**asdict(z))
        if len(self.bars)>=3:
            a=self.bars[-3]
            d=1 if a.high<b.low else (-1 if a.low>b.high else 0)
            if d:
                lo,hi=(a.high,b.low) if d==1 else (b.high,a.low)
                f={'id':f'F{self.minutes}:{b.time.isoformat()}','direction':d,'low':lo,'high':hi,
                   'available_at':b.end,'origin':a.time,'fill':0,'invalid':False}
                self.fvgs.append(f);emit('FVG',**f)
        # Separate geometries; strategies default to pivot zones rather than silently mixing them.
        if len(self.bars)>=4:
            base=self.bars[-4:-1]
            base_lo=min(x.low for x in base);base_hi=max(x.high for x in base)
            compact=all(abs(x.close-x.open)/max(x.high-x.low,1e-12)<=self.cfg['base_body_max'] for x in base)
            strong=abs(b.close-b.open)/max(b.high-b.low,1e-12)>=self.cfg['impulse_body_min']
            d=1 if b.close>base_hi+margin else (-1 if b.close<base_lo-margin else 0)
            if compact and strong and d and base_hi>base_lo:
                incoming=1 if base[-1].close>=base[0].open else -1
                pattern=('Rally' if incoming==1 else 'Drop')+'–Base–'+('Rally' if d==1 else 'Drop')
                z=Zone(f'B{self.minutes}:{base[0].time.isoformat()}:{d}',d,base_lo,base_hi,base[0].time,b.end,'base',pattern)
                self.zones.append(z);emit('ZONE_ACTIVE',**asdict(z))
        pivot_zones=[z for z in self.zones if z.zone_kind=='pivot' and z.available_at==b.end]
        for z in pivot_zones:
            p=self.bars[-2]
            low,high=(p.low,min(p.open,p.close)) if z.direction==1 else (max(p.open,p.close),p.high)
            if high>low:
                f=Zone(z.id.replace('Z','W',1),z.direction,low,high,z.origin,b.end,'fractal_wick',z.pattern)
                self.zones.append(f);emit('ZONE_ACTIVE',**asdict(f))
        return events

def fibonacci(start,end,depth):
    if not 0<=depth<=1 or start==end:
        raise ValueError('Ancrage/degré Fibonacci invalide')
    return end-(end-start)*depth

def volume_profile(bars, available_at, volume_kind, bins=32, area=.70):
    if volume_kind not in ('ticks','transactions'):
        return {'enabled':False,'reason':'Volume compatible absent'}
    if not bars or any(b.end>available_at for b in bars):
        raise ValueError('Profil futur ou vide interdit')
    if not isinstance(bins,int) or bins<1:raise ValueError('Nombre de bins invalide')
    lo,hi=min(b.low for b in bars),max(b.high for b in bars)
    if hi<=lo or not 0<area<=1:
        raise ValueError('Profil sans étendue ou proportion invalide')
    volumes=[0.]*bins
    for b in bars:
        first=max(0,min(bins-1,int((b.low-lo)/(hi-lo)*bins)))
        last=max(first,min(bins-1,int((b.high-lo)/(hi-lo)*bins)))
        for i in range(first,last+1):
            volumes[i]+=b.volume/(last-first+1)
    if not sum(volumes):
        return {'enabled':False,'reason':'Volumes nuls'}
    poc=max(range(bins),key=lambda i:volumes[i]);a=z=poc;total=volumes[poc]
    while total<area*sum(volumes) and (a>0 or z<bins-1):
        if a>0 and (z==bins-1 or volumes[a-1]>=volumes[z+1]):
            a-=1;total+=volumes[a]
        else:
            z+=1;total+=volumes[z]
    step=(hi-lo)/bins
    return {'enabled':True,'poc':lo+(poc+.5)*step,'val':lo+a*step,'vah':lo+(z+1)*step,
            'available_at':available_at,'volume_kind':volume_kind,
            'approximation':'Volume réparti uniformément entre low/high de chaque M1; VA contiguë autour du POC'}
