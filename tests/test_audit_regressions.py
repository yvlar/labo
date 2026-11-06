"""Audit indépendant : données synthétiques de tests, aucun résultat de marché."""
import json
import unittest
from copy import deepcopy
from datetime import timedelta
from dataclasses import replace
from pathlib import Path
from lab.data import validate_instrument
from lab.engine import Engine
from lab.execution import Broker, Intent
from lab.primitives import Pivot, Zone, Structure, fibonacci
from tests.test_lab import ROOT, START, cfg, spec, bar


def variant(family):
    c=json.loads((ROOT/'configs/variants.json').read_text())
    c['models']=[next(m for m in c['models'] if m['family']==family)]
    c['gold']['guards']['enabled']=False
    return c


class AuditRegressions(unittest.TestCase):
    def test_caller_cannot_mutate_frozen_engine_parameters(self):
        config=cfg();instrument=spec();e=Engine(config,instrument)
        config['risk']['slippage_ticks']=999
        config['models'][0]['stop_variant']='confirmation'
        instrument['tick_size']=1
        self.assertEqual(e.broker.cfg['slippage_ticks'],1)
        self.assertEqual(e.models[0].cfg['stop_variant'],'range')
        self.assertEqual(e.broker.spec['tick_size'],.01)

    def test_gap_over_partial_and_target_still_respects_quantities(self):
        risk=deepcopy(cfg()['risk']);risk['slippage_ticks']=0
        broker=Broker(risk,spec()|{'commission_per_unit':0},lambda *a,**k:None)
        broker.submit(Intent('partial-gap','test',1,'market',100,99,104,START,START+timedelta(hours=1),'E4',{}))
        broker.on_bar(bar(0,100,100.5,99.5,100,spread=0));initial=broker.position['risk_initial']
        broker.on_bar(bar(1,105,106,104,105,spread=0))
        self.assertEqual(len(broker.trades[0]['exits']),2)
        self.assertAlmostEqual(sum(x['gross'] for x in broker.trades[0]['exits'])/initial,3)

    def test_known_opening_partial_precedes_later_stop(self):
        risk=deepcopy(cfg()['risk']);risk['slippage_ticks']=0
        broker=Broker(risk,spec()|{'commission_per_unit':0},lambda *a,**k:None)
        broker.submit(Intent('partial-stop','test',1,'market',100,99,110,START,START+timedelta(hours=1),'E4',{}))
        broker.on_bar(bar(0,100,100.5,99.5,100,spread=0));initial=broker.position['risk_initial']
        broker.on_bar(bar(1,103,104,98,100,spread=0))
        self.assertAlmostEqual(sum(x['gross'] for x in broker.trades[0]['exits'])/initial,.5)

    def test_m2_refinement_preserves_the_parent_external_target(self):
        e=Engine(variant('M2'),spec());m=e.models[0];b=bar(0,130,131,129,130)
        h=e.structures[240];h.trend=1
        h.zones=[Zone('parent',1,90,110,START-timedelta(hours=4),b.end,'pivot','Drop–Base–Rally')]
        h.pivots=[Pivot('internal',1,100,START-timedelta(days=1),START,'H'),Pivot('external',1,150,START-timedelta(days=1),START,'HH')]
        t=START-timedelta(hours=3)
        e.structures[60].zones=[Zone('mid',1,91,109,t,t+timedelta(hours=1),'pivot','Drop–Base–Rally')]
        e.structures[30].zones=[Zone('entry',1,92,94,t,t+timedelta(minutes=30),'pivot','Drop–Base–Rally')]
        m.on_bar(b,[])
        self.assertEqual(e.broker.orders[0].target,150)

    def test_known_opening_target_precedes_a_later_stop(self):
        broker=Broker(cfg()['risk'],spec(),lambda *a,**k:None)
        broker.submit(Intent('gap-target','test',1,'market',100,99,102,START,START+timedelta(hours=1),'E2',{}))
        broker.on_bar(bar(0,100,100.5,99.5,100))
        broker.on_bar(bar(1,103,104,98,100))
        self.assertEqual(broker.trades[0]['exits'][0]['reason'],'TARGET_OPEN')

    def test_m5b_weak_third_candle_is_not_strong_confirmation(self):
        e=Engine(cfg('M5B'),spec())
        data=[bar(i) for i in range(5)]+[bar(5,100,101,99.8,100.8),bar(6,100.8,104,100.7,103.8),
                                        bar(7,104,106,103,104.1)]
        for b in data:e.push(b)
        self.assertFalse(e.broker.orders)

    def test_intrabar_exit_does_not_free_position_at_earlier_open(self):
        c=cfg('M5A');c['models'].append(next(m for m in json.loads((ROOT/'configs/primary.json').read_text())['models'] if m['family']=='M5B'))
        data=[bar(i) for i in range(5)]+[bar(5,100,101,99.8,100.8),bar(6,100.8,104,100.7,103.8),
            bar(7,104,106,103,105.8),bar(8,105.8,106,100.8,102.5),bar(9,102.5,106.5,102.4,106.4),bar(10,106.4,130,105.5,120)]
        e=Engine(c,spec())
        for b in data:e.push(b)
        opened=[x for x in e.events if x['kind']=='OPEN']
        self.assertEqual([x['strategy'] for x in opened],['M5B-80-range'])

    def test_fixed_r_exit_does_not_require_structural_target(self):
        c=cfg('M1');c['models'][0]['exit']='E2';e=Engine(c,spec());b=bar(0)
        self.assertTrue(e.models[0].order(b,1,100,99,100,'limit',{}))
        self.assertEqual(e.broker.orders[0].target,102)

    def setup_ote(self):
        e=Engine(variant('M3'),spec());model=e.models[0];b=bar(30,110,111,109,110)
        h=e.structures[60];h.trend=1
        h.pivots=[Pivot('target',1,140,START-timedelta(hours=1),START,'HH')]
        zone=Zone('HTF',1,90,112,START-timedelta(hours=1),START,'pivot','Drop–Base–Rally')
        model.context={'zone':zone,'touch':START+timedelta(minutes=20),'direction':1}
        l=e.structures[5];p=Pivot('anchor',-1,90,START+timedelta(minutes=15),START+timedelta(minutes=25),'LL')
        l.pivots=[p]
        l.bars=[replace(bar(15,92,95,90,94),minutes=5),
                replace(bar(20,94,115,93,114),minutes=5),
                replace(bar(26,114,120,95,110),minutes=5)]
        events=[{'tf':5,'kind':'CHoCH','direction':1,'pivot_id':'broken'}]
        return e,model,b,l,events

    def test_ote_anchor_uses_the_ltf_impulse_not_last_m1_wick(self):
        e,m,b,l,events=self.setup_ote();m.on_bar(b,events)
        self.assertEqual(e.broker.orders[0].reasons['anchors'],[90,120])
        self.assertAlmostEqual(e.broker.orders[0].entry,fibonacci(90,120,.702)+.1)

    def test_ote_cannot_ignore_a_fvg_earlier_in_same_impulse(self):
        e,m,b,l,events=self.setup_ote()
        l.fvgs=[{'id':'earlier','direction':1,'origin':l.pivots[0].pivot_time,'available_at':START+timedelta(minutes=25),
                 'low':96,'high':97,'invalid':False,'fill':0}]
        m.on_bar(b,events)
        self.assertEqual(e.broker.orders,[])

    def test_sweep_can_reintegrate_on_later_bar_within_bound(self):
        s=Structure(1,cfg()['primitives'])
        for b in [bar(0,h=101),bar(1,h=103),bar(2,h=102),bar(3,102,105,101,104),bar(4,104,104.5,101,102)]:
            events=s.push(b)
        self.assertTrue(any(x['kind']=='SWEEP' for x in events))

    def test_m6_retest_below_broken_level_is_not_long_confirmation(self):
        e=Engine(variant('M6C'),spec());m=e.models[0];b=bar(30,98,101,98,99.9)
        h=e.structures[60];h.trend=1;h.pivots=[Pivot('target',1,120,START-timedelta(hours=2),START,'HH')]
        z=Zone('HTF',1,90,105,START-timedelta(hours=2),START,'pivot','Drop–Base–Rally')
        c={'zone':z,'touch':START,'direction':1,'choch_at':START,'broken':{'level':100,'time':b.time-timedelta(minutes=5)}}
        l=e.structures[5]
        l.bars=[replace(bar(i,99,100,98,99.1),minutes=5) for i in (5,10,15)]
        l.bars.append(replace(b,time=b.end-timedelta(minutes=5),minutes=5))
        m.candles(b,[],c)
        self.assertEqual(e.broker.orders,[])

    def test_cad_account_cannot_be_silently_valued_in_usd(self):
        with self.assertRaises(ValueError):validate_instrument(spec()|{'account_currency':'CAD'})

    def test_canonical_label_does_not_allow_etf_provider_symbol(self):
        with self.assertRaises(ValueError):validate_instrument(spec()|{'provider_symbol':'GLD'})

    def test_half_at_two_r_then_entry_gives_one_r_gross(self):
        risk=deepcopy(cfg()['risk']);risk['slippage_ticks']=0
        instrument=spec()|{'commission_per_unit':0}
        b=Broker(risk,instrument,lambda *a,**k:None)
        b.submit(Intent('weighted','test',1,'market',100,99,110,START,START+timedelta(hours=1),'E4',{}))
        b.on_bar(bar(0,100,100.5,99.5,100,spread=0))
        qty=b.position['qty'];initial=b.position['risk_initial']
        b.on_bar(bar(1,100,102.1,99.9,102,spread=0));b.on_bar(bar(2,100,100.1,99.9,100,spread=0))
        self.assertEqual(b.trades[0]['qty'],qty)
        self.assertAlmostEqual(sum(x['gross'] for x in b.trades[0]['exits'])/initial,1)


if __name__=='__main__':unittest.main()
