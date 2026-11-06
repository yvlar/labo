"""Scénarios Gold synthétiques : causalité, unités et protections, aucune performance de marché."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from lab.data import UTC, canonical, validate_instrument
from lab.engine import Engine, validate_config
from lab.execution import Broker, Intent
from lab.gold import GoldDesk, contract_status, market_access
from tests.test_lab import START, bar, cfg, opr_fixture, spec


def gold_cfg(models=False):
    c=cfg();c['gold']['guards']['enabled']=True
    c['gold']['atr_period']=3;c['gold']['regime_lookback']=4
    if not models:c['models']=[]
    return c


def gold_spec():
    return spec()|{'market_sessions':[{'weekdays':list(range(7)),'start':'00:00','end':'00:00','timezone':'UTC'}],
                  'market_sessions_source':'TEST : calendrier synthétique 24h'}


def gold_bar(i,spread=.1,**kwargs):
    return bar(i,o=2000,h=2001,l=1999,c=2000,spread=spread,**kwargs)


class GoldContractTests(unittest.TestCase):
    def test_gold_units_and_point_value_must_agree(self):
        for change in ({'base_currency':'XAG'},{'price_unit':'cents'},{'quantity_unit':'lots sans définition'},
                       {'contract_size':100,'point_value':1},{'product_type':'future'},{'product_type':'etf'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_instrument(gold_spec()|change)

    def test_verified_market_contract_requires_provider_calendar(self):
        metadata=gold_spec()|{'synthetic':False,'verified':True,'product_type':'cfd'}
        validate_instrument(metadata)
        with self.assertRaises(ValueError):validate_instrument(metadata|{'market_sessions':[]})
        with self.assertRaises(ValueError):validate_instrument(metadata|{'market_sessions_source':''})

    def test_invalid_calendar_and_future_closure_are_rejected(self):
        for sessions in ([{'weekdays':[7],'start':'00:00','end':'00:00','timezone':'UTC'}],
                         [{'weekdays':[0],'start':'08:00','end':'17:00','timezone':'INVALID'}]):
            with self.assertRaises(ValueError):validate_instrument(gold_spec()|{'market_sessions':sessions})
        closure={'start':START.isoformat(),'end':(START+timedelta(hours=1)).isoformat(),
                 'available_at':(START+timedelta(minutes=1)).isoformat(),'source':'TEST','reason':'fixture'}
        with self.assertRaises(ValueError):validate_instrument(gold_spec()|{'market_closures':[closure]})

    def test_tick_value_and_sizing_use_ounces_per_contract(self):
        s=gold_spec()|{'contract_size':100,'point_value':100,'qty_step':.01,'min_qty':.01}
        self.assertAlmostEqual(contract_status(s)['usd_per_tick_per_contract'],1)
        b=Broker(cfg()['risk'],s,lambda *a,**k:None)
        b.submit(Intent('contract-test','test',1,'market',2000.1,1999,2005,START,START+timedelta(minutes=30),'E2',{}))
        b.on_bar(bar(0,2000,2000.5,1999.5,2000))
        p=b.position;self.assertIsNotNone(p)
        self.assertAlmostEqual(p['risk_initial'],(p['entry']-1999)*p['qty']*100)
        self.assertLessEqual(p['risk_initial'],250)
        self.assertAlmostEqual(p['qty']/.01,round(p['qty']/.01))

    def test_profile_rejects_hidden_or_incomplete_filters(self):
        for change in ({'atr_period':0},{'regime_high':.5},{'unknown_rule':1}):
            c=gold_cfg();c['gold'].update(change)
            with self.assertRaises(ValueError):validate_config(c)
        c=gold_cfg();c['gold']['usd_calendar']['enabled']=True
        with self.assertRaises(ValueError):validate_config(c)


class GoldCausalityTests(unittest.TestCase):
    def test_atr_warmup_and_gap_require_observed_contiguous_bars(self):
        e=Engine(gold_cfg(),gold_spec())
        for i in range(2):e.push(gold_bar(i));self.assertIsNone(e.gold.context['atr_m1_usd_per_ounce'])
        e.push(gold_bar(2));self.assertEqual(e.gold.context['atr_m1_usd_per_ounce'],2)
        e.push(gold_bar(4));self.assertIsNone(e.gold.context['atr_m1_usd_per_ounce'])

    def test_fill_guard_uses_previous_atr_and_new_opening_spread(self):
        e=Engine(gold_cfg(),gold_spec())
        for i in range(3):e.push(gold_bar(i))
        e.broker.submit(Intent('test','test',1,'market',2000.1,1990,2020,gold_bar(2).end,START+timedelta(minutes=30),'E2',{}))
        # Huge future intrabar range must not make the opening spread look cheap.
        e.push(bar(3,2000,2300,1999,2200,spread=1.2))
        refused=next(x for x in e.events if x['kind']=='ORDER_REFUSED')
        self.assertIn('ATR Gold',refused['reason'])
        self.assertEqual(refused['gold_check']['checks']['atr_m1_usd_per_ounce'],2)
        self.assertEqual(refused['gold_check']['checks']['atr_available_at'],gold_bar(2).end)
        self.assertIsNone(e.broker.position)

    def test_gold_signal_refusal_is_explained(self):
        e=Engine(gold_cfg(models=True),gold_spec());b=gold_bar(0);e.push(b)
        self.assertFalse(e.models[0].order(b,1,2000.1,1999,2005,'market',{}))
        self.assertEqual(e.events[-1]['kind'],'GOLD_SIGNAL_REFUSED')
        self.assertIn('ATR',e.events[-1]['reason'])

    def test_tick_margins_follow_the_actual_gold_contract(self):
        s=gold_spec()|{'tick_size':.1};e=Engine(gold_cfg(),s)
        self.assertEqual(e.effective_primitives['break_margin'],.1)
        self.assertEqual(e.effective_primitives['equal_tolerance'],.5)

    def test_previous_session_is_invisible_until_complete(self):
        start=datetime(2025,1,6,tzinfo=UTC);e=Engine(gold_cfg(),gold_spec())
        for i in range(479):e.push(gold_bar(i,start=start))
        self.assertNotIn('ASIE',e.gold.context['previous_sessions'])
        e.push(gold_bar(479,start=start))
        previous=e.gold.context['previous_sessions']['ASIE']
        self.assertEqual(previous['bars'],480)
        self.assertEqual(previous['available_at'],start+timedelta(hours=8))

    def test_incomplete_session_never_publishes_extremes(self):
        start=datetime(2025,1,6,tzinfo=UTC);e=Engine(gold_cfg(),gold_spec())
        for i in range(480):
            if i!=200:e.push(gold_bar(i,start=start))
        self.assertNotIn('ASIE',e.gold.context['previous_sessions'])
        self.assertTrue(any(x['kind']=='GOLD_SESSION_INCOMPLETE' for x in e.events))

    def test_london_new_york_overlap_respects_different_dst_dates(self):
        for day,expected in [(17,True),(31,False)]:
            start=datetime(2025,3,day,16,tzinfo=UTC);e=Engine(gold_cfg(),gold_spec())
            e.push(gold_bar(0,start=start));sessions=e.gold.context['active_sessions']
            self.assertIn('NEW_YORK',sessions)
            self.assertEqual('LONDRES' in sessions,expected)

    def test_frozen_context_and_future_mutation_prefix_invariance(self):
        data=[gold_bar(i) for i in range(10)]
        a=Engine(gold_cfg(),gold_spec())
        for b in data[:5]:a.push(b)
        events=canonical(a.events);context=canonical(a.gold.snapshot())
        for b in data[5:]:a.push(b)
        other=Engine(gold_cfg(),gold_spec())
        for b in data[:5]:other.push(b)
        self.assertEqual(events,canonical([x for x in a.events if x['available_at']<=data[4].end]))
        self.assertEqual(context,canonical(other.gold.snapshot()))

    def test_volatility_regime_is_context_only_and_causal(self):
        e=Engine(gold_cfg(),gold_spec())
        for i in range(7):e.push(gold_bar(i))
        previous=deepcopy(e.gold.context)
        e.push(bar(7,2000,2020,1980,2000))
        self.assertEqual(e.gold.context['volatility_regime'],'ÉLEVÉE')
        self.assertEqual(e.gold.context['atr_reference'],2)
        self.assertEqual(previous['atr_m1_usd_per_ounce'],2)


class GoldProtectionTests(unittest.TestCase):
    def test_spread_and_minimum_stop_refusals(self):
        e=Engine(gold_cfg(),gold_spec())
        for i in range(3):e.push(gold_bar(i))
        at=e.last.end
        self.assertIn('stop Gold',e.gold.guard(at,.5,2000,1999)['reason'])
        self.assertIn('minimum en ticks',e.gold.guard(at,.001,2000,1999.99)['reason'])

    def test_market_hours_overnight_and_close_buffer(self):
        s=gold_spec()|{'market_sessions':[{'weekdays':[6],'start':'18:00','end':'17:00','timezone':'America/New_York'}]}
        self.assertTrue(market_access(s,datetime(2025,3,10,13,tzinfo=UTC))['open'])
        close=datetime(2025,3,10,20,58,tzinfo=UTC)
        self.assertTrue(market_access(s,close,5)['near_close'])
        self.assertFalse(market_access(s,datetime(2025,3,10,21,tzinfo=UTC))['open'])

    def test_known_holiday_closure_and_buffer(self):
        at=START;closure={'start':(at+timedelta(minutes=3)).isoformat(),
            'end':(at+timedelta(hours=1)).isoformat(),'available_at':(at-timedelta(hours=1)).isoformat(),
            'reason':'TEST fermeture','source':'TEST'}
        s=gold_spec()|{'market_closures':[closure]};validate_instrument(s)
        self.assertTrue(market_access(s,at,5)['near_close'])
        self.assertFalse(market_access(s,at+timedelta(minutes=3))['open'])

    def test_usd_calendar_respects_information_availability(self):
        c=gold_cfg();c['gold']['guards']['require_atr']=False
        c['gold']['usd_calendar'].update(enabled=True,events=[{'id':'TEST','title':'Annonce synthétique de test',
            'currency':'USD','scheduled_at':START.isoformat(),'available_at':(START-timedelta(hours=1)).isoformat(),'source':'TEST ONLY'}])
        e=Engine(c,gold_spec())
        self.assertIsNone(e.gold.news(START-timedelta(hours=2))['next'])
        self.assertFalse(e.gold.guard(START-timedelta(minutes=16),.1,2000,1999)['reason'].startswith('Fenêtre'))
        self.assertIn('Annonce',e.gold.news(START-timedelta(minutes=10))['next']['title'])
        self.assertIn('annonce USD',e.gold.guard(START-timedelta(minutes=10),.1,2000,1999)['reason'])

    def test_protective_exit_still_executes_when_entry_conditions_deteriorate(self):
        e=Engine(gold_cfg(),gold_spec())
        for i in range(3):e.push(gold_bar(i))
        e.broker.submit(Intent('test','test',1,'market',2000.1,1990,2020,e.last.end,START+timedelta(minutes=30),'E2',{}))
        e.push(gold_bar(3));self.assertIsNotNone(e.broker.position)
        e.push(bar(4,1980,1985,1979,1982,spread=5))
        self.assertEqual(e.broker.trades[0]['exits'][0]['reason'],'STOP')
        self.assertLess(e.broker.trades[0]['exits'][0]['price'],1990)

    def test_m5_gold_path_includes_context_and_fill_checks(self):
        c=gold_cfg(models=True);e=Engine(c,gold_spec())
        start=START-timedelta(minutes=14)
        for i in range(14):e.push(gold_bar(i,start=start))
        for b in opr_fixture():
            from dataclasses import replace
            e.push(replace(b,**{k:getattr(b,k)+1900 for k in ('open','high','low','close','ask_open','ask_high','ask_low','ask_close')}))
        self.assertEqual(len(e.broker.trades),1)
        t=e.broker.trades[0]
        self.assertIsNotNone(t['reasons']['gold_context']['atr_m1_usd_per_ounce'])
        self.assertTrue(t['gold_fill_check']['allowed'])
        self.assertLessEqual(t['gold_fill_check']['checks']['atr_available_at'],t['opened_at'])


if __name__=='__main__':unittest.main()
