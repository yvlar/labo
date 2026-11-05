"""Toutes les données de ce fichier sont SYNTHÉTIQUES et réservées aux tests logiciels."""
import csv
import json
import math
import random
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from lab.data import Bar,UTC,Resampler,canonical,check,import_file
from lab.engine import Engine,validate_config
from lab.execution import Broker,Intent
from lab.primitives import Structure,Zone,Pivot,volume_profile,fibonacci
from lab.storage import Journal
from lab.research import metrics,preregister
from lab.cli import ROOT

def cfg(family='M5A'):
    c=json.loads((ROOT/'configs/primary.json').read_text())
    c['models']=[next(m for m in c['models'] if m['family']==family)]
    if family=='M1':c['models'][0]['setup_ttl_minutes']=60
    c['primitives']['pivot_left']=c['primitives']['pivot_right']=1
    return c

def spec():
    return json.loads((ROOT/'configs/instrument.example.json').read_text())|{
        'provider':'TEST-SYNTHETIC','synthetic':True,'verified':True,
        'product_type':'fixture','point_value':1,'min_qty':1,'qty_step':1,
        'margin_rate':.01,'commission_per_unit':.02}

START=datetime(2025,1,6,14,30,tzinfo=UTC)
def bar(i,o=100,h=101,l=99,c=100,start=START,spread=.1):
    return Bar(start+timedelta(minutes=i),o,h,l,c,o+spread,h+spread,l+spread,c+spread)

def opr_fixture():
    data=[bar(i,100,101,99,100) for i in range(5)]
    data += [bar(5,100,103,100,102.5),bar(6,102.5,103,100.8,101.6),
             bar(7,101.6,104.2,101.5,104),bar(8,104,105,103,104.5),
             bar(9,104.5,116,104,115)]
    return data

def expand_candle(t,o,h,l,c,n):
    values=[]
    for i in range(n):
        pos=(i+1)/n
        if pos<=.25:v=o+(h-o)*pos/.25
        elif pos<=.5:v=h+(l-h)*(pos-.25)/.25
        else:v=l+(c-l)*(pos-.5)/.5
        values.append(v)
    values[n//4-1]=h;values[n//2-1]=l;values[-1]=c
    result=[];prev=o
    for i,v in enumerate(values):
        result.append(bar(i,prev,max(prev,v),min(prev,v),v,start=t));prev=v
    return result

def m1_fixture():
    start=datetime(2025,1,6,0,tzinfo=UTC);result=[]
    candles=[(100,110,95,108),(108,120,105,118),(118,119,110,112),
             (112,130,111,128),(128,130,120,126),(126,140,121,138),(138,139,131,133)]
    for i,c in enumerate(candles):result+=expand_candle(start+timedelta(hours=i),*c,60)
    ltf=[(133,134,130,131),(131,132,128,129),(129,130,127,128),(128,131,128,130),
         (130,130.5,126,126.5),(126.5,129,126.3,128),(128,128.5,127,127.8),
         (127.8,133,127.7,132.5),(132.5,133,128,129),(129,141,128.9,140.5)]
    for i,c in enumerate(ltf):result+=expand_candle(start+timedelta(hours=7,minutes=5*i),*c,5)
    return result

class CausalityTests(unittest.TestCase):
    def test_pivot_invisible_until_confirmation(self):
        s=Structure(1,cfg()['primitives']);s.push(bar(0,h=101));s.push(bar(1,h=105))
        self.assertFalse(s.pivots)
        s.push(bar(2,h=102));p=next(p for p in s.pivots if p.side==1)
        self.assertEqual(p.pivot_time,START+timedelta(minutes=1))
        self.assertEqual(p.available_at,START+timedelta(minutes=3))

    def test_zone_only_after_impulse(self):
        s=Structure(1,cfg()['primitives']);s.push(bar(0,100,102,98,100.1));self.assertFalse(s.zones)
        s.push(bar(1,100.1,106,100,105.5));self.assertEqual(len([z for z in s.zones if z.zone_kind=='pivot']),1)
        self.assertEqual(s.zones[0].available_at,START+timedelta(minutes=2))

    def test_fvg_third_close_and_fill(self):
        s=Structure(1,cfg()['primitives']);s.push(bar(0,100,101,99,100));s.push(bar(1,100,104,100,103))
        self.assertFalse(s.fvgs)
        s.push(bar(2,103,105,102,104));self.assertEqual(s.fvgs[0]['available_at'],START+timedelta(minutes=3))
        s.push(bar(3,103,104,101.5,103));self.assertAlmostEqual(s.fvgs[0]['fill'],.5)

    def test_htf_complete_and_gap(self):
        r=Resampler(5)
        for i in range(4):self.assertIsNone(r.push(bar(i)))
        self.assertEqual(r.push(bar(4)).minutes,5)
        r=Resampler(5)
        for i in [0,1,3,4]:self.assertIsNone(r.push(bar(i)))

    def test_opr_only_at_end_and_dst(self):
        for start in [START,datetime(2025,7,7,13,30,tzinfo=UTC)]:
            e=Engine(cfg(),spec())
            for i in range(4):e.push(bar(i,start=start))
            self.assertFalse(any(x['kind']=='OPR_READY' for x in e.events))
            e.push(bar(4,start=start));event=next(x for x in e.events if x['kind']=='OPR_READY')
            self.assertEqual(event['available_at'],start+timedelta(minutes=5))

    def test_no_future_volume_profile(self):
        with self.assertRaises(ValueError):volume_profile([bar(1)],bar(1).time,'ticks')
        self.assertFalse(volume_profile([bar(1)],bar(1).end,'absent')['enabled'])
        p=volume_profile([replace(bar(1),volume=50)],bar(1).end,'ticks')
        self.assertTrue(p['enabled']);self.assertIn('uniformément',p['approximation'])

    def test_prefix_invariance_with_future_mutation(self):
        for family,fixture in [('M1',m1_fixture()),('M5A',opr_fixture()),('M5B',opr_fixture())]:
            full=Engine(cfg(family),spec())
            for b in fixture:full.push(b)
            for n in [len(fixture)//2,len(fixture)-2]:
                prefix=Engine(cfg(family),spec())
                for b in fixture[:n]:prefix.push(b)
                until=fixture[n-1].end
                expected=[x for x in full.events if x['available_at']<=until]
                self.assertEqual(canonical(prefix.events),canonical(expected))
                altered=Engine(cfg(family),spec())
                for b in fixture[:n]+[replace(b,open=b.open+500,close=b.close+500,high=b.high+500,low=b.low+500,
                        ask_open=b.ask_open+500,ask_close=b.ask_close+500,ask_high=b.ask_high+500,ask_low=b.ask_low+500) for b in fixture[n:]]:
                    altered.push(b)
                self.assertEqual(canonical(prefix.events),canonical([x for x in altered.events if x['available_at']<=until]))

    def test_batch_stream_parity_and_restart(self):
        fixture=opr_fixture();c=cfg();s=spec();full=Engine(c,s)
        for b in fixture:full.push(b)
        with tempfile.TemporaryDirectory() as folder:
            j=Journal(Path(folder)/'journal.sqlite',{'config':c,'spec':s});first=Engine(c,s)
            for b in fixture[:8]:j.append(first,b)
            j.close();j=Journal(Path(folder)/'journal.sqlite',{'config':c,'spec':s})
            restored=Engine(c,s);j.restore(restored)
            for b in fixture:j.append(restored,b)
            self.assertEqual(canonical(full.events),canonical(restored.events))
            self.assertEqual(canonical(full.snapshot()),canonical(restored.snapshot()))
            self.assertFalse(j.append(restored,fixture[-1]))
            with self.assertRaises(ValueError):j.append(restored,replace(fixture[-1],close=114))
            j.close()

    def test_persistent_break_is_not_sweep(self):
        s=Structure(1,cfg()['primitives'])
        for b in [bar(0,h=101),bar(1,h=103),bar(2,h=102),bar(3,102,105,101,104)]:s.push(b)
        self.assertIsNone(s.last_sweep)

class ExecutionTests(unittest.TestCase):
    def broker(self,policy='E2'):
        events=[];b=Broker(cfg()['risk'],spec(),lambda kind,at,**x:events.append((kind,at,x)))
        b.submit(Intent('test','test',1,'market',100,99,102,START+timedelta(minutes=1),START+timedelta(minutes=30),policy,{}))
        return b,events

    def test_decision_next_quote_and_bidask(self):
        b,events=self.broker();b.on_bar(bar(0,100,100.5,99.5,100));self.assertIsNone(b.position)
        b.on_bar(bar(1,100,100.5,99.5,100));self.assertAlmostEqual(b.position['entry'],100.11)
        self.assertGreater(b.position['risk_initial'],0)
        self.assertLessEqual(b.position['risk_initial'],250)

    def test_stop_target_ambiguous_stop_first(self):
        b,ev=self.broker();b.on_bar(bar(1,100,104,98,101))
        self.assertEqual(b.ambiguous,1);self.assertEqual(b.trades[0]['exits'][0]['reason'],'STOP')
        self.assertLess(b.trades[0]['net_r'],-1)

    def test_gap_stop_at_worse_quote(self):
        b,ev=self.broker();b.on_bar(bar(1,100,100.5,99.5,100));b.on_bar(bar(2,97,98,96,97))
        self.assertAlmostEqual(b.trades[0]['exits'][0]['price'],96.99)

    def test_limit_touch_does_not_guarantee_fill(self):
        b,ev=self.broker();b.orders[0].kind='limit';b.orders[0].entry=100
        b.on_bar(bar(1,101,102,99.9,101));self.assertIsNone(b.position)
        b.on_bar(bar(2,101,102,99.88,101));self.assertIsNotNone(b.position)

    def test_partial_and_net_break_even(self):
        b,ev=self.broker('E4');b.orders[0].target=110
        b.on_bar(bar(1,100,100.5,99.5,100));p=b.position;px=p['entry'];r=p['unit_risk']
        b.on_bar(bar(2,100.5,px+2*r+.1,100.4,102))
        self.assertTrue(b.position['partial_done']);self.assertEqual(b.position['stop'],px)
        b.on_bar(bar(3,px,px+.5,px-.5,px))
        t=b.trades[0];self.assertEqual(len(t['exits']),2)
        self.assertLess(t['exits'][1]['gross'],0)
        self.assertAlmostEqual(t['net'],sum(x['gross']-x['fee'] for x in t['exits'])-t['qty']*.02)

    def test_quantity_and_margin_refusal(self):
        b,ev=self.broker();b.spec['min_qty']=1000000;b.on_bar(bar(1,100,101,99.5,100))
        self.assertIsNone(b.position);self.assertTrue(any(x[0]=='ORDER_REFUSED' for x in ev))

    def test_incident_does_not_erase_position(self):
        b,ev=self.broker();b.on_bar(bar(1,100,100.5,99.5,100));self.assertIsNotNone(b.position)
        b.on_bar(bar(2,100,100.5,99.5,100),False);self.assertIsNotNone(b.position)
        b.on_bar(bar(3,98,100,97,99),False);self.assertEqual(len(b.trades),1)

    def test_daily_block_and_expiry(self):
        b,ev=self.broker();b.daily_locked=True;b.day=START.date();b.on_bar(bar(1))
        self.assertIsNone(b.position)
        b,ev=self.broker();b.orders[0].expires=START+timedelta(minutes=1);b.on_bar(bar(1))
        self.assertTrue(any(x[0]=='EXPIRED' for x in ev))

    def test_funding_and_conversion(self):
        b,ev=self.broker();b.spec['financing_per_unit_day']=.1
        b.on_bar(bar(1,100,100.5,99.5,100));fee=b.fees
        b.on_bar(bar(1441,100,100.5,99.5,100));self.assertGreater(b.fees,fee)
        s=spec();s['currency']='EUR'
        with self.assertRaises(ValueError):Engine(cfg(),s)

class IntegrationTests(unittest.TestCase):
    def test_m2_extreme_selection_without_choch(self):
        c=json.loads((ROOT/'configs/variants.json').read_text())
        c['models']=[next(m for m in c['models'] if m['family']=='M2')]
        e=Engine(c,spec());m=e.models[0];b=bar(0,130,131,129,130)
        h=e.structures[240];h.trend=1
        z=Zone('parent',1,90,110,START-timedelta(hours=4),b.end,'pivot','Drop–Base–Rally')
        h.zones=[z];h.pivots=[Pivot('target',1,150,START-timedelta(days=1),START-timedelta(hours=2),'HH')]
        t=START-timedelta(hours=3)
        e.structures[60].zones=[Zone('mid',1,91,109,t,t+timedelta(hours=1),'pivot','Drop–Base–Rally')]
        e.structures[30].zones=[Zone('higher',1,100,105,t,t+timedelta(minutes=30),'pivot','Drop–Base–Rally'),
                               Zone('lowest',1,92,94,t,t+timedelta(minutes=30),'pivot','Drop–Base–Rally')]
        m.on_bar(b,[])
        self.assertEqual(e.broker.orders[0].reasons['entry_zone'],'lowest')
        self.assertNotIn('choch',e.broker.orders[0].reasons)

    def test_immutable_strategy_identity_on_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'j.sqlite';j=Journal(path,{'version':'one'});j.close()
            with self.assertRaises(ValueError):Journal(path,{'version':'two'})

    def test_all_variants_prefix_invariance(self):
        c=json.loads((ROOT/'configs/variants.json').read_text());data=m1_fixture();n=440
        for m in c['models']:
            config=deepcopy(c);config['models']=[m]
            a,b=Engine(config,spec()),Engine(config,spec())
            for bar_ in data:a.push(bar_)
            for bar_ in data[:n]:b.push(bar_)
            self.assertEqual(canonical(b.events),canonical([e for e in a.events if e['available_at']<=data[n-1].end]),m['id'])

    def test_invalid_instrument_fails_closed(self):
        for key,value in [('tick_size',0),('margin_rate',2),('commission_per_unit',-1),('point_value',float('inf'))]:
            s=spec();s[key]=value
            with self.assertRaises(ValueError):Engine(cfg(),s)

    def test_m5a_end_to_end(self):
        e=Engine(cfg(),spec())
        for b in opr_fixture():e.push(b)
        self.assertEqual(len(e.broker.trades),1)
        o=next(x for x in e.events if x['kind']=='ENTRY_PENDING')
        fill=next(x for x in e.events if x['kind']=='OPEN')
        self.assertEqual(o['available_at'],bar(7).end)
        self.assertEqual(fill['fill_time'],bar(8).time)

    def test_m5b_fvg_next_open(self):
        e=Engine(cfg('M5B'),spec());data=[bar(i) for i in range(5)]
        data += [bar(5,100,101,99.8,100.8),bar(6,100.8,104,100.7,103.8),
                 bar(7,104,106,103,105.8),bar(8,108,109,107,108.5)]
        for b in data:e.push(b)
        order=next(x for x in e.events if x['kind']=='ENTRY_PENDING')
        fill=next(x for x in e.events if x['kind']=='OPEN')
        self.assertEqual(order['available_at'],bar(7).end)
        self.assertAlmostEqual(fill['fill'],108.11)
        self.assertNotEqual(fill['fill'],data[7].close)

    def test_m1_end_to_end(self):
        e=Engine(cfg('M1'),spec())
        for b in m1_fixture():e.push(b)
        pending=[x for x in e.events if x['kind']=='ENTRY_PENDING']
        self.assertTrue(pending,'M1 doit produire un ordre dans le scénario causal contrôlé')
        self.assertTrue(e.broker.trades,'M1 doit exécuter et clôturer dans ce scénario')
        self.assertIn('choch',pending[0]['reasons'])

    def test_refuse_real_accounts_and_endpoints(self):
        for key,value in [('mode','live'),('account_type','demo'),('account_type','real'),('endpoint','https://api.broker.com')]:
            c=cfg();c['execution'][key]=value
            with self.assertRaises(ValueError):Engine(c,spec())

    def test_invalid_data_and_incomplete(self):
        for data in [[bar(1),bar(1)],[bar(2),bar(1)],[replace(bar(1),close=500)],
                     [replace(bar(1),ask_low=1)],[replace(bar(1),open=math.nan)]]:
            with self.assertRaises(ValueError):check(data)
        with self.assertRaises(ValueError):check([bar(1)],bar(1).time)

    def test_import_hash_and_synthetic_reporting_block(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);raw=path/'input.csv';meta=path/'meta.json'
            with raw.open('w') as f:
                w=csv.DictWriter(f,fieldnames=list(bar(0).record()));w.writeheader();w.writerows(x.record() for x in opr_fixture())
            meta.write_text(canonical(spec()));dest=import_file(raw,meta,path)
            self.assertTrue((dest/'manifest.json').exists());self.assertTrue(list((path/'data/raw').iterdir()))
            with self.assertRaises(ValueError):preregister(path,ROOT/'configs/primary.json',dest,ROOT/'configs/splits.example.json','forbidden')

    def test_statistics_no_fabricated_profit(self):
        m=metrics([],[],1000);self.assertIsNone(m['expectancy_net_r']);self.assertIsNone(m['win_rate'])

    def test_fibonacci_fixed_convention(self):
        self.assertAlmostEqual(fibonacci(100,110,.702),102.98)
        self.assertAlmostEqual(fibonacci(110,100,.702),107.02)

    def test_all_variants_configured_and_run(self):
        c=json.loads((ROOT/'configs/variants.json').read_text());validate_config(c)
        e=Engine(c,spec())
        for b in m1_fixture():e.push(b)
        self.assertTrue(e.events)

if __name__=='__main__':unittest.main()
