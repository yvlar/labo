"""Contexte causal XAU/USD. Conventions du projet, jamais un calibrage rentable déclaré."""
from collections import deque
from copy import deepcopy
from datetime import datetime, time, timedelta
from math import isfinite
from statistics import mean, median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .data import UTC, dt


SESSION_WINDOWS = (
    ('ASIE', 'Asia/Tokyo', '09:00', '17:00'),
    ('LONDRES', 'Europe/London', '08:00', '16:30'),
    ('NEW_YORK', 'America/New_York', '08:00', '17:00'),
)


def clock(value):
    result=time.fromisoformat(value)
    if result.tzinfo is not None or result.second or result.microsecond:
        raise ValueError('Horaire local HH:MM sans fuseau requis')
    return result


def validate_market_sessions(sessions):
    if not isinstance(sessions,list):raise ValueError('market_sessions doit être une liste')
    for session in sessions:
        try:
            ZoneInfo(session['timezone']);clock(session['start']);clock(session['end'])
            days=session['weekdays']
            if not days or any(type(d) is not int or not 0<=d<=6 for d in days):
                raise ValueError('Jours de cotation invalides : lundi=0, dimanche=6')
        except (KeyError,TypeError,ZoneInfoNotFoundError) as e:
            raise ValueError('Calendrier fournisseur invalide ou incomplet') from e


def interval(day,zone,start,end):
    a=datetime.combine(day,clock(start),ZoneInfo(zone))
    b=datetime.combine(day,clock(end),ZoneInfo(zone))
    if b<=a:b+=timedelta(days=1)
    return a.astimezone(UTC),b.astimezone(UTC)


def market_access(spec,at,buffer_minutes=0):
    sessions=spec.get('market_sessions',[])
    if not sessions:return {'known':False,'open':None,'reason':'Calendrier fournisseur absent'}
    known_closures=[c for c in spec.get('market_closures',[]) if dt(c['available_at'])<=at]
    for closure in known_closures:
        if dt(closure['start'])<=at<dt(closure['end']):
            return {'known':True,'open':False,'reason':'Fermeture fournisseur : '+closure['reason']}
    for session in sessions:
        local=at.astimezone(ZoneInfo(session['timezone']))
        for day in (local.date(),local.date()-timedelta(days=1)):
            if day.weekday() not in session['weekdays']:continue
            start,end=interval(day,session['timezone'],session['start'],session['end'])
            if start<=at<end:
                future=[dt(c['start']) for c in known_closures if at<dt(c['start'])<end]
                if future:end=min(future)
                near=end-at<=timedelta(minutes=buffer_minutes)
                return {'known':True,'open':True,'session_end':end,'near_close':near,
                        'reason':'Approche fermeture / pause fournisseur' if near else 'Cotation ouverte'}
    return {'known':True,'open':False,'reason':'Hors horaires de cotation du fournisseur'}


def validate_profile(profile):
    required={'version','atr_period','regime_lookback','regime_low','regime_high',
              'break_margin_ticks','equal_tolerance_ticks','guards','usd_calendar'}
    if not isinstance(profile,dict) or set(profile)!=required:
        raise ValueError('Profil Gold requis et clés strictement définies')
    for key in ('atr_period','regime_lookback'):
        if type(profile[key]) is not int or profile[key]<2:raise ValueError('Fenêtre Gold invalide : '+key)
    for key in ('regime_low','regime_high','break_margin_ticks','equal_tolerance_ticks'):
        if type(profile[key]) not in (int,float) or not isfinite(profile[key]) or profile[key]<=0:
            raise ValueError('Seuil Gold invalide : '+key)
    if not profile['regime_low']<1<profile['regime_high']:
        raise ValueError('Bornes de régime Gold invalides')
    g=profile['guards']
    if set(g)!={'enabled','require_atr','max_spread_to_atr','max_spread_to_stop','min_stop_ticks','close_buffer_minutes'}:
        raise ValueError('Protections Gold invalides')
    if any(type(g[k]) is not bool for k in ('enabled','require_atr')):raise ValueError('Booléens Gold requis')
    for key in ('max_spread_to_atr','max_spread_to_stop','min_stop_ticks','close_buffer_minutes'):
        if type(g[key]) not in (int,float) or not isfinite(g[key]) or g[key]<0:
            raise ValueError('Protection Gold invalide : '+key)
    if not 0<g['max_spread_to_atr']<=1 or not 0<g['max_spread_to_stop']<1 or g['min_stop_ticks']<1:
        raise ValueError('Ratios spread/stop Gold invalides')
    news=profile['usd_calendar']
    if set(news)!={'enabled','before_minutes','after_minutes','events'} or type(news['enabled']) is not bool:
        raise ValueError('Calendrier USD invalide')
    for key in ('before_minutes','after_minutes'):
        if type(news[key]) not in (int,float) or not isfinite(news[key]) or news[key]<0:
            raise ValueError('Fenêtre de prudence USD invalide')
    if not isinstance(news['events'],list):raise ValueError('Liste des annonces USD requise')
    if news['enabled'] and not news['events']:raise ValueError('Filtre USD activé sans calendrier renseigné')
    ids=set()
    for event in news['events']:
        if event.get('currency')!='USD' or not event.get('id') or event['id'] in ids or not event.get('source') or not event.get('title'):
            raise ValueError('Annonce USD sans identifiant unique, titre ou provenance')
        ids.add(event['id']);scheduled=dt(event['scheduled_at']);available=dt(event['available_at'])
        if available>scheduled:raise ValueError('Annonce prévue connue seulement après publication : inutilisable')


def contract_status(spec):
    blockers=[]
    if not spec.get('verified'):blockers.append('Spécifications fournisseur non vérifiées')
    if not spec.get('market_sessions'):blockers.append('Horaires de cotation fournisseur à renseigner')
    if not spec.get('market_sessions_source'):blockers.append('Provenance des horaires manquante')
    return {'symbol':'XAUUSD','status':'À CONFIGURER' if blockers else 'SPÉCIFICATIONS RENSEIGNÉES',
        'blockers':blockers,'product_type':spec.get('product_type'),
        'provider':spec.get('provider'),'provider_symbol':spec.get('provider_symbol'),
        'account_currency':spec.get('account_currency'),
        'price_unit':'USD par once troy','quantity_unit':'contrat',
        'ounces_per_contract':spec.get('contract_size'),
        'usd_per_tick_per_contract':spec.get('tick_size',0)*spec.get('point_value',0),
        'specifications_verified':bool(spec.get('verified')),'market_data_checked':False,
        'note':'La vérification des spécifications ne prouve aucune performance.'}


class GoldDesk:
    def __init__(self,profile,spec,emit):
        validate_profile(profile)
        self.profile,self.spec,self.emit=deepcopy(profile),deepcopy(spec),emit
        self.ranges=deque(maxlen=profile['atr_period'])
        self.atr_history=deque(maxlen=profile['regime_lookback'])
        self.last_close=None;self.last_at=None;self.context=None
        self.sessions={};self.previous_sessions={}

    def gap(self):
        self.ranges.clear();self.atr_history.clear();self.last_close=None;self.context=None
        for value in self.sessions.values():value['complete']=False

    def news(self,at):
        c=self.profile['usd_calendar']
        known=[x for x in c['events'] if dt(x['available_at'])<=at]
        upcoming=sorted([x for x in known if dt(x['scheduled_at'])>=at],key=lambda x:dt(x['scheduled_at']))
        blackout=[x['id'] for x in known if dt(x['scheduled_at'])-timedelta(minutes=c['before_minutes'])<=at<=dt(x['scheduled_at'])+timedelta(minutes=c['after_minutes'])]
        return {'enabled':c['enabled'],'configured':bool(c['events']),
                'next':deepcopy(upcoming[0]) if upcoming else None,'blackout_ids':blackout if c['enabled'] else []}

    def update(self,b):
        true_range=b.high-b.low if self.last_close is None else max(b.high-b.low,abs(b.high-self.last_close),abs(b.low-self.last_close))
        self.ranges.append(true_range);self.last_close=b.close
        atr=mean(self.ranges) if len(self.ranges)==self.ranges.maxlen else None
        reference=median(self.atr_history) if len(self.atr_history)==self.atr_history.maxlen else None
        regime='INDÉTERMINÉ'
        if atr is not None and reference is not None and reference>0:
            regime='FAIBLE' if atr<reference*self.profile['regime_low'] else ('ÉLEVÉE' if atr>reference*self.profile['regime_high'] else 'NORMALE')
        if atr is not None:self.atr_history.append(atr)
        active=[]
        for name,zone,start,end in SESSION_WINDOWS:
            local=b.time.astimezone(ZoneInfo(zone))
            a,z=interval(local.date(),zone,start,end)
            old=self.sessions.get(name)
            if old and b.time>=old['end']:
                self.finish(name,old,b.end);del self.sessions[name]
            if local.weekday()<5 and a<=b.time<z and b.end<=z:
                active.append(name)
                item=self.sessions.get(name)
                if item is None:
                    item={'start':a,'end':z,'high':b.high,'low':b.low,'bars':0,'last':None,
                          'complete':b.time==a,'timezone':zone}
                    self.sessions[name]=item
                if item['last'] and item['last']!=b.time:item['complete']=False
                item['high']=max(item['high'],b.high);item['low']=min(item['low'],b.low)
                item['bars']+=1;item['last']=b.end
                if b.end==z:
                    self.finish(name,item,b.end);del self.sessions[name]
        spread=b.ask_close-b.close
        self.last_at=b.end
        self.context={'available_at':b.end,'atr_m1_usd_per_ounce':atr,'atr_period':self.profile['atr_period'],
            'atr_reference':reference,'volatility_regime':regime,'spread_usd_per_ounce':spread,
            'spread_ticks':spread/self.spec['tick_size'],'spread_to_atr':spread/atr if atr and atr>0 else None,
            'active_sessions':active,'session_bucket':next((s for s in ('NEW_YORK','LONDRES','ASIE') if s in active),'HORS_FENÊTRES'),
            'previous_sessions':deepcopy(self.previous_sessions),
            'market_access':market_access(self.spec,b.end,self.profile['guards']['close_buffer_minutes']),
            'usd_calendar':self.news(b.end),'session_convention':'Fenêtres de contexte du projet, sans attribution aux horaires S6'}
        return self.context

    def finish(self,name,item,available_at):
        expected=int((item['end']-item['start']).total_seconds()/60)
        complete=item['complete'] and item['bars']==expected and item['last']==item['end']
        if complete:
            obj={k:item[k] for k in ('start','end','high','low','bars','timezone')}
            obj['available_at']=available_at
            self.previous_sessions[name]=obj
            self.emit('GOLD_SESSION_COMPLETE',available_at,session=name,**obj)
        else:self.emit('GOLD_SESSION_INCOMPLETE',available_at,session=name,bars=item['bars'],expected=expected,
                       reason='Extrêmes non publiés : session incomplète')

    def guard(self,at,spread,entry,stop):
        g=self.profile['guards'];distance=abs(entry-stop)
        atr=self.context.get('atr_m1_usd_per_ounce') if self.context else None
        checks={'at':at,'spread_usd_per_ounce':spread,'stop_usd_per_ounce':distance,
                'spread_to_stop':spread/distance if distance else None,
                'spread_to_atr':spread/atr if atr and atr>0 else None,
                'atr_available_at':self.last_at,'atr_m1_usd_per_ounce':atr}
        reason=None
        access=market_access(self.spec,at,g['close_buffer_minutes'])
        news=self.news(at)
        if not g['enabled']:return {'allowed':True,'reason':'Contexte Gold en observation','checks':checks}
        if not access['known'] and not self.spec.get('synthetic'):reason='Calendrier fournisseur inconnu'
        elif access['known'] and not access['open']:reason=access['reason']
        elif access.get('near_close'):reason=access['reason']
        elif news['blackout_ids']:reason='Fenêtre annonce USD : '+', '.join(news['blackout_ids'])
        elif g['require_atr'] and (atr is None or atr<=0):reason='Historique insuffisant pour ATR Gold'
        elif distance<g['min_stop_ticks']*self.spec['tick_size']:reason='Stop Gold inférieur au minimum en ticks'
        elif distance<=0 or spread/distance>g['max_spread_to_stop']:reason='Spread trop élevé par rapport au stop Gold'
        elif atr and atr>0 and spread/atr>g['max_spread_to_atr']:reason='Spread trop élevé par rapport à ATR Gold'
        return {'allowed':reason is None,'reason':reason or 'Protections Gold satisfaites','checks':checks}

    def fill_guard(self,b,order,price):
        # ATR is from the PREVIOUS closed M1; only the new opening bid/ask is observed here.
        return self.guard(b.time,b.ask_open-b.open,price,order.stop)

    def snapshot(self):
        return {'contract':contract_status(self.spec),'context':deepcopy(self.context),
                'guards_enabled':self.profile['guards']['enabled'],'profile':deepcopy(self.profile)}
