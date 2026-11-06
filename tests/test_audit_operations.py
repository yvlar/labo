"""Épreuves opérationnelles et comptables de l'audit; aucune donnée de marché inventée."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from lab.data import canonical,check
from lab.engine import Engine
from lab.live import StreamingSession
from lab.storage import Journal
from lab.research import stress_bar,opportunity_metrics,evaluation_verdict
from lab.primitives import Zone,Pivot
from tests.test_lab import cfg,spec,bar,START,m1_fixture,opr_fixture,ROOT,expand_candle
from tests.test_audit_regressions import variant


class AuditOperations(unittest.TestCase):
    def test_small_sample_is_not_called_a_method_failure(self):
        self.assertEqual(evaluation_verdict({'trades':1,'daily_bootstrap_expectancy_ci95':[-1,-.5]},100),'non concluant')
        self.assertEqual(evaluation_verdict({'trades':100,'daily_bootstrap_expectancy_ci95':[-1,-.5]},100),'échec')

    def test_h4_m15_confirmation_path_executes_only_after_confirmation(self):
        c=cfg('M1');c['models'][0].update(id='M1-H4-M15',htf=240,ltf=15,setup_ttl_minutes=180)
        start=START.replace(hour=0,minute=0);data=[]
        htf=[(100,110,95,108),(108,120,105,118),(118,119,110,112),(112,130,111,128),
             (128,130,120,126),(126,140,121,138),(138,139,131,133)]
        for i,candle in enumerate(htf):data+=expand_candle(start+timedelta(minutes=240*i),*candle,240)
        ltf=[(133,134,130,131),(131,132,128,129),(129,130,127,128),(128,131,128,130),
             (130,130.5,126,126.5),(126.5,129,126.3,128),(128,128.5,127,127.8),
             (127.8,133,127.7,132.5),(132.5,133,128,129),(129,141,128.9,140.5)]
        for i,candle in enumerate(ltf):data+=expand_candle(start+timedelta(minutes=1680+15*i),*candle,15)
        e=Engine(c,spec())
        for b in data:e.push(b)
        order=next(x for x in e.events if x['kind']=='ENTRY_PENDING')
        choch=[x for x in e.events if x['kind']=='CHoCH' and x.get('tf')==15 and x.get('direction')==1]
        self.assertTrue(any(x['available_at']==order['available_at'] for x in choch))
        self.assertTrue(e.broker.trades)

    def test_m6_reversal_context_is_explicit_and_not_continuation(self):
        c=variant('M6A');c['models'][0]['context_mode']='reversal';e=Engine(c,spec());m=e.models[0]
        h=e.structures[60];h.trend=-1
        h.zones=[Zone('opposite',1,95,101,START-timedelta(hours=1),START,'pivot','Drop–Base–Rally')]
        m.on_bar(bar(0),[]);self.assertIsNotNone(m.context)
        m.on_bar(bar(1),[]);self.assertIsNotNone(m.context)
        self.assertFalse(e.broker.orders)

    def test_m1_touch_without_choch_has_no_order(self):
        data=m1_fixture()[:438];last=data[-1]
        data += [bar(i,130,130.5,129.5,130,start=last.end) for i in range(70)]
        e=Engine(cfg('M1'),spec())
        for b in data:e.push(b)
        self.assertTrue(any(x['kind']=='ZONE_TOUCHED' and x['strategy'].startswith('M1') for x in e.events))
        self.assertFalse(any(x['kind']=='ENTRY_PENDING' for x in e.events))

    def test_stale_feed_blocks_new_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            j=Journal(Path(folder)/'j.sqlite',{});session=StreamingSession(cfg(),spec(),j)
            for b in opr_fixture():session.ingest(canonical(b.record()),b.end+timedelta(minutes=10))
            self.assertEqual(session.status,'STALE')
            self.assertFalse(any(x['kind']=='OPEN' for x in session.engine.events));j.close()

    def test_halt_latch_survives_restart_and_keeps_position(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'j.sqlite';j=Journal(path,{});session=StreamingSession(cfg(),spec(),j)
            data=opr_fixture()
            for b in data[:9]:session.ingest(canonical(b.record()),b.end+timedelta(seconds=1))
            self.assertIsNotNone(session.engine.broker.position)
            session.ingest('{}',data[8].end);self.assertTrue(session.halted);j.close()
            j=Journal(path,{});restarted=StreamingSession(cfg(),spec(),j)
            self.assertTrue(restarted.halted);self.assertIsNotNone(restarted.engine.broker.position)
            restarted.ingest(canonical(data[9].record()),data[9].end+timedelta(seconds=1))
            self.assertTrue(restarted.engine.broker.trades)
            self.assertEqual(restarted.health_at(data[9].end),'HALTED');j.close()

    def test_duplicates_and_gap_preserve_deterministic_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            j=Journal(Path(folder)/'j.sqlite',{});s=StreamingSession(cfg(),spec(),j)
            for b in opr_fixture()[:8]:s.ingest(canonical(b.record()),b.end+timedelta(seconds=1))
            before=len(s.engine.events);b=opr_fixture()[7]
            self.assertFalse(s.ingest(canonical(b.record()),b.end+timedelta(seconds=1)))
            self.assertEqual(len(s.engine.events),before)
            b=bar(10,104,105,103,104)
            s.ingest(canonical(b.record()),b.end+timedelta(seconds=1))
            self.assertTrue(any(x['kind']=='DATA_GAP' for x in s.engine.events))
            self.assertFalse(s.engine.broker.orders);j.close()

    def test_cost_stress_preserves_ohlc_envelope(self):
        b=replace(bar(0,100,110,99,109),ask_open=105,ask_high=111,ask_low=100,ask_close=110)
        stretched=stress_bar(b,3);check([stretched])
        self.assertEqual(stretched.ask_open,115)
        self.assertGreaterEqual(stretched.ask_high,stretched.ask_open)

    def test_no_fill_counts_against_opportunity_denominator(self):
        c=cfg();e=Engine(c,spec())
        for b in opr_fixture()[:8]:e.push(b)
        m=opportunity_metrics(e.events,[],START,START+timedelta(hours=2))
        self.assertEqual(m['eligible_opportunities'],1)
        self.assertEqual(m['submitted_signals'],1)
        self.assertEqual(m['filled_orders'],0)
        self.assertEqual(m['pending_or_open_at_boundary'],1)
        self.assertEqual(m['net_r_per_eligible_opportunity_observed'],0)

    def test_m2_sell_selects_highest_known_child_and_ignores_future(self):
        e=Engine(variant('M2'),spec());m=e.models[0];b=bar(0,150,151,149,150)
        h=e.structures[240];h.trend=-1
        h.zones=[Zone('parent',-1,100,140,START-timedelta(hours=4),b.end,'pivot','Rally–Base–Drop')]
        h.pivots=[Pivot('target',-1,80,START-timedelta(days=1),START,'LL')]
        t=START-timedelta(hours=3)
        e.structures[60].zones=[Zone('middle',-1,105,139,t,t+timedelta(hours=1),'pivot','Rally–Base–Drop')]
        e.structures[30].zones=[Zone('low',-1,110,115,t,t+timedelta(minutes=30),'pivot','Rally–Base–Drop'),
            Zone('high',-1,128,135,t,t+timedelta(minutes=30),'pivot','Rally–Base–Drop'),
            Zone('future',-1,130,138,t,b.end+timedelta(minutes=1),'pivot','Rally–Base–Drop')]
        m.on_bar(b,[])
        self.assertEqual(e.broker.orders[0].reasons['entry_zone'],'high')

    def test_opr_m15_unavailable_before_0945(self):
        e=Engine(variant('M4B'),spec())
        for i in range(14):e.push(bar(i))
        self.assertFalse(any(x['kind']=='OPR_READY' for x in e.events))
        e.push(bar(14));event=next(x for x in e.events if x['kind']=='OPR_READY')
        self.assertEqual(event['available_at'],START+timedelta(minutes=15))

    def test_direct_reference_and_m1_share_parent_opportunity(self):
        config=cfg('M1');direct=json.loads(canonical(config));direct['models'][0]['family']='SD_DIRECT';direct['models'][0]['id']='DIRECT'
        engines=[Engine(c,spec()) for c in (config,direct)]
        for e in engines:
            h=e.structures[60];h.trend=1
            h.zones=[Zone('shared-parent',1,90,100,START-timedelta(hours=1),bar(0).end,'pivot','Drop–Base–Rally')]
            h.pivots=[Pivot('target',1,120,START-timedelta(hours=2),START,'HH')]
            e.models[0].on_bar(bar(0,105,106,104,105),[])
        self.assertEqual([x['opportunity_id'] for x in engines[0].events if x['kind']=='OPPORTUNITY'],
                         [x['opportunity_id'] for x in engines[1].events if x['kind']=='OPPORTUNITY'])
        self.assertFalse(engines[0].broker.orders);self.assertTrue(engines[1].broker.orders)


if __name__=='__main__':unittest.main()
