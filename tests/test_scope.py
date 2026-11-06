"""Restrictions d'instrument; métadonnées et prix synthétiques de tests uniquement."""
import json
import tempfile
import unittest
from pathlib import Path
from lab.data import canonical, digest, import_file, validate_instrument
from lab.engine import Engine
from lab.execution import Broker
from lab.live import run_live
from lab.research import evaluate, preregister, verify_dataset
from lab.server import validate_run_scope
from tests.test_lab import ROOT, cfg, spec


class XauOnlyTests(unittest.TestCase):
    def test_supported_pair_remains_usable(self):
        validate_instrument(spec())
        self.assertEqual(Engine(cfg(),spec()).spec['symbol'],'XAUUSD')

    def test_engine_and_broker_refuse_other_symbols(self):
        for symbol in ('EURUSD','GBPUSD','XAGUSD','GC','GLD','NQ','XAUUSDm','XAU/USD','',None):
            with self.subTest(symbol=symbol):
                metadata=spec()|{'symbol':symbol}
                with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                    Engine(cfg(),metadata)
                with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                    Broker(cfg()['risk'],metadata,lambda *args,**kwargs:None)

    def test_import_rejected_before_reading_or_archiving_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);meta=root/'meta.json'
            meta.write_text(canonical(spec()|{'symbol':'EURUSD'}))
            with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                import_file(root/'unread.csv',meta,root)
            self.assertFalse((root/'data').exists())

    def test_preregistration_and_dataset_validation_reject_other_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);dataset=root/'dataset';dataset.mkdir()
            manifest={'metadata':spec()|{'symbol':'EURUSD'}}
            (dataset/'manifest.json').write_text(canonical(manifest))
            with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                preregister(root,ROOT/'configs/primary.json',dataset,root/'unread-splits.json','blocked')
            with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                verify_dataset(dataset,manifest)
            self.assertFalse((root/'runs').exists())

    def test_evaluation_refused_before_consuming_test_or_writing_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'runs/blocked';run.mkdir(parents=True)
            frozen={'manifest':{'metadata':spec()|{'symbol':'EURUSD'}}}
            frozen['hash']=digest(frozen)
            (run/'preregistration.json').write_text(canonical(frozen))
            with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                evaluate(root,'blocked')
            self.assertFalse((run/'test-access.json').exists())
            self.assertFalse((run/'report.json').exists())

    def test_live_refused_before_creating_prospective_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);meta=root/'meta.json'
            meta.write_text(canonical(spec()|{'symbol':'NQ'}))
            with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                run_live(root,ROOT/'configs/primary.json',meta,root/'unread.jsonl','blocked',seconds=.01)
            self.assertFalse((root/'runs').exists())

    def test_existing_archives_remain_unchanged_when_outside_scope(self):
        for name in ('history.json','identity.json','snapshot.json','report.json'):
            with self.subTest(artifact=name), tempfile.TemporaryDirectory() as folder:
                run=Path(folder)
                def document(metadata):
                    if name=='history.json':return {'manifest':{'metadata':metadata}}
                    if name=='report.json':return {'preregistration':{'manifest':{'metadata':metadata}}}
                    return {'instrument':metadata}
                path=run/name;path.write_text(canonical(document(spec())))
                validate_run_scope(run)
                original=canonical(document(spec()|{'symbol':'EURUSD'}))
                path.write_text(original)
                with self.assertRaisesRegex(ValueError,'exclusivement XAU/USD'):
                    validate_run_scope(run)
                self.assertEqual(path.read_text(),original)


if __name__=='__main__':unittest.main()
