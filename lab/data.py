"""M1 UTC, timestamps d'ouverture; aucune réparation silencieuse."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import shutil
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
SUPPORTED_SYMBOL = 'XAUUSD'

def dt(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Horodatage sans fuseau interdit')
    return result.astimezone(UTC)

def canonical(value):
    def encode(x):
        if is_dataclass(x): return asdict(x)
        if isinstance(x, (datetime,)): return x.isoformat()
        if hasattr(x, 'isoformat'): return x.isoformat()
        raise TypeError(type(x).__name__)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=encode, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    ask_open: float
    ask_high: float
    ask_low: float
    ask_close: float
    volume: float = 0
    minutes: int = 1

    def __post_init__(self):
        # Stable representation across CSV/JSON and in-memory replay (100 == 100.0).
        for key in ('open','high','low','close','ask_open','ask_high','ask_low','ask_close','volume'):
            object.__setattr__(self,key,float(getattr(self,key)))

    @property
    def end(self):
        return self.time + timedelta(minutes=self.minutes)

    def record(self):
        return asdict(self) | {'time': self.time.isoformat()}

    @classmethod
    def parse(cls, row):
        return cls(dt(row['time']), **{k: float(row[k]) for k in
                   ('open','high','low','close','ask_open','ask_high','ask_low','ask_close')},
                   volume=float(row.get('volume') or 0), minutes=int(row.get('minutes') or 1))

def validate_bar(b):
    values = [b.open,b.high,b.low,b.close,b.ask_open,b.ask_high,b.ask_low,b.ask_close,b.volume]
    if not all(math.isfinite(v) for v in values) or min(values[:-1]) <= 0 or b.volume < 0:
        raise ValueError('Prix/volume impossible')
    for o,h,l,c in [(b.open,b.high,b.low,b.close),(b.ask_open,b.ask_high,b.ask_low,b.ask_close)]:
        if not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError('OHLC incohérent')
    if any(a < bid for a,bid in [(b.ask_open,b.open),(b.ask_high,b.high),
                                 (b.ask_low,b.low),(b.ask_close,b.close)]):
        raise ValueError('Ask inférieur au bid')
    if b.minutes != 1 or b.time.second or b.time.microsecond:
        raise ValueError('Seules les bougies M1 alignées sont acceptées')

def read_csv(path):
    with Path(path).open(newline='') as f:
        return [Bar.parse(r) for r in csv.DictReader(f)]

def check(bars, as_of=None):
    gaps = []
    previous = None
    for b in bars:
        validate_bar(b)
        if previous and b.time <= previous.time:
            raise ValueError('Doublon ou ordre temporel incorrect : import refusé')
        if as_of and b.end > as_of:
            raise ValueError('Bougie incomplète ou future')
        if previous and b.time != previous.end:
            gaps.append({'start': previous.end.isoformat(), 'end': b.time.isoformat(),
                         'minutes': (b.time-previous.end).total_seconds()/60})
        previous = b
    if not bars:
        raise ValueError('Aucune bougie')
    return {'bars': len(bars), 'gaps': gaps, 'policy': 'aucun comblement; HTF/OPR incomplets rejetés'}

def validate_instrument(meta):
    if meta.get('symbol') != SUPPORTED_SYMBOL:
        raise ValueError('Laboratoire exclusivement XAU/USD : symbole XAUUSD requis')
    if meta.get('currency')!='USD' or meta.get('price_kind')!='bid_ask':
        raise ValueError('Seuls USD et bid/ask séparés sont pris en charge')
    for key in ['tick_size','point_value','contract_size','min_qty','qty_step','margin_rate']:
        if not isinstance(meta.get(key),(int,float)) or not math.isfinite(meta[key]) or meta[key]<=0:
            raise ValueError('Spécification instrument invalide : '+key)
    if meta['margin_rate']>1:raise ValueError('Taux de marge hors intervalle (0,1]')
    for key in ['commission_per_unit','financing_per_unit_day']:
        if not isinstance(meta.get(key),(int,float)) or not math.isfinite(meta[key]) or meta[key]<0:
            raise ValueError('Coût instrument invalide : '+key)
    if meta.get('volume_kind') not in {'absent','ticks','transactions'}:
        raise ValueError('Nature du volume inconnue')
    if meta.get('base_currency')!='XAU' or meta.get('price_unit')!='USD_per_troy_ounce' or meta.get('quantity_unit')!='contract':
        raise ValueError('Contrat Gold : XAU, prix USD par once troy et quantités en contrats requis')
    if meta.get('product_type') not in {'spot_otc','cfd'} and not (meta.get('synthetic') is True and meta.get('product_type')=='fixture'):
        raise ValueError('Produit Gold autorisé : spot_otc ou cfd explicitement identifié')
    if not math.isclose(meta['point_value'],meta['contract_size'],rel_tol=1e-9,abs_tol=1e-12):
        raise ValueError('Valeur du point Gold incohérente avec les onces troy par contrat')
    from .gold import validate_market_sessions
    validate_market_sessions(meta.get('market_sessions',[]))
    closures=meta.get('market_closures',[])
    if not isinstance(closures,list):raise ValueError('Liste de fermetures fournisseur invalide')
    for closure in closures:
        if not closure.get('source') or not closure.get('reason') or not (
                dt(closure['available_at'])<=dt(closure['start'])<dt(closure['end'])):
            raise ValueError('Fermeture fournisseur sans provenance ou chronologie valide')
    if meta.get('verified') and not meta.get('synthetic') and (
            not meta.get('market_sessions') or not meta.get('market_sessions_source')):
        raise ValueError('Horaires Gold et leur provenance requis avant validation du fournisseur')

def import_file(source, metadata, root):
    meta = json.loads(Path(metadata).read_text())
    required = ['provider','symbol','product_type','currency','price_kind','volume_kind',
                'synthetic','provenance','calendar','timezone','tick_size','point_value',
                'contract_size','min_qty','qty_step','margin_rate','commission_per_unit',
                'financing_per_unit_day','verified']
    missing = [k for k in required if k not in meta]
    if missing:
        raise ValueError('Métadonnées manquantes : '+', '.join(missing))
    validate_instrument(meta)
    if meta['price_kind'] != 'bid_ask' or meta['timezone'] != 'UTC':
        raise ValueError('Import : bid/ask séparés et UTC requis')
    if not isinstance(meta['synthetic'], bool) or not isinstance(meta['verified'], bool):
        raise ValueError('synthetic/verified doivent être des booléens')
    for key in ['tick_size','point_value','contract_size','min_qty','qty_step','margin_rate']:
        if not math.isfinite(meta[key]) or meta[key] <= 0:
            raise ValueError('Spécification instrument invalide : '+key)
    for key in ['commission_per_unit','financing_per_unit_day']:
        if not math.isfinite(meta[key]) or meta[key] < 0:
            raise ValueError('Coût invalide : '+key)
    if Path(source).suffix.lower() == '.parquet':
        try:
            import pandas as pd
            bars = [Bar.parse(r) for r in pd.read_parquet(source).to_dict('records')]
        except ImportError as e:
            raise ValueError('Parquet nécessite pandas et pyarrow; utiliser CSV sinon') from e
    else:
        bars = read_csv(source)
    quality = check(bars, datetime.now(UTC))
    raw_hash = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    dataset_hash = digest({'bars': [b.record() for b in bars], 'metadata': meta})
    root = Path(root)
    raw = root/'data/raw'/raw_hash
    raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        shutil.copyfile(source, raw)
    dest = root/'data/normalized'/dataset_hash
    dest.mkdir(parents=True, exist_ok=True)
    with (dest/'bars.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(bars[0].record()))
        w.writeheader()
        w.writerows(b.record() for b in bars)
    manifest = {'hash':dataset_hash,'raw_hash':raw_hash,'metadata':meta,'quality':quality,
                'period':[bars[0].time.isoformat(),bars[-1].end.isoformat()]}
    (dest/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return dest

class Resampler:
    def __init__(self, minutes):
        self.minutes, self.bucket = minutes, []

    def push(self, b):
        # UTC fixed boundaries. H4/D1 sessions are explicitly UTC in this implementation.
        minute = int(b.time.timestamp()/60)
        start = minute//self.minutes*self.minutes
        if self.bucket and (int(self.bucket[0].time.timestamp()/60)//self.minutes*self.minutes != start
                            or b.time != self.bucket[-1].end):
            self.bucket = []
        self.bucket.append(b)
        if (minute+1) % self.minutes:
            return None
        items, self.bucket = self.bucket, []
        if len(items) != self.minutes or int(items[0].time.timestamp()/60) != start:
            return None
        return Bar(items[0].time,items[0].open,max(x.high for x in items),min(x.low for x in items),
                   items[-1].close,items[0].ask_open,max(x.ask_high for x in items),
                   min(x.ask_low for x in items),items[-1].ask_close,sum(x.volume for x in items),self.minutes)
