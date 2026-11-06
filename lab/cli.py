import argparse
import json
from pathlib import Path
from .data import import_file,canonical
from .research import preregister,evaluate,verify_dataset,revision
from .engine import validate_config

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description='Laboratoire OlinVest, exclusivement simulé')
    sub=p.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import-data');imp.add_argument('--file',required=True);imp.add_argument('--metadata',required=True)
    pre=sub.add_parser('preregister')
    for k in ['config','dataset','splits','experiment']:pre.add_argument('--'+k,required=True)
    ev=sub.add_parser('evaluate');ev.add_argument('--experiment',required=True)
    hist=sub.add_parser('history')
    for k in ['config','dataset','experiment']:hist.add_argument('--'+k,required=True)
    live=sub.add_parser('live')
    for k in ['config','metadata','feed','experiment']:live.add_argument('--'+k,required=True)
    live.add_argument('--seconds',type=float,default=10);live.add_argument('--max-age',type=float,default=90)
    probe=sub.add_parser('probe');probe.add_argument('--feed',required=True)
    probe.add_argument('--seconds',type=float,default=3);probe.add_argument('--output',default='reports/live-probe.json')
    web=sub.add_parser('serve');web.add_argument('--host',default='127.0.0.1');web.add_argument('--port',type=int,default=8080)
    check=sub.add_parser('check-config');check.add_argument('--config',default='configs/primary.json')
    gold=sub.add_parser('gold-status');gold.add_argument('--config',default='configs/primary.json')
    gold.add_argument('--metadata',default='configs/instrument.example.json')
    a=p.parse_args()
    try:
        if hasattr(a,'experiment') and (Path(a.experiment).name!=a.experiment or a.experiment in ('.','..')):
            raise ValueError('Nom d’expérience invalide')
        if a.command=='import-data':print(import_file(a.file,a.metadata,ROOT))
        elif a.command=='preregister':print(preregister(ROOT,a.config,a.dataset,a.splits,a.experiment))
        elif a.command=='evaluate':print(evaluate(ROOT,a.experiment))
        elif a.command=='gold-status':
            from .data import validate_instrument
            from .gold import contract_status
            cfg=json.loads(Path(a.config).read_text());validate_config(cfg)
            spec=json.loads(Path(a.metadata).read_text());validate_instrument(spec)
            print(canonical({'contract':contract_status(spec),'profile':cfg['gold'],
                'market_connection_checked':False,'performance_evaluated_by_this_command':False}))
        elif a.command=='check-config':
            validate_config(json.loads(Path(a.config).read_text()));print('Configuration valide · simulateur interne uniquement')
        elif a.command=='history':
            cfg=json.loads(Path(a.config).read_text());validate_config(cfg)
            manifest=json.loads((Path(a.dataset)/'manifest.json').read_text());verify_dataset(a.dataset,manifest)
            if manifest['metadata']['synthetic'] or not manifest['metadata']['verified']:
                raise ValueError('Rejeu utilisateur réservé aux données de marché vérifiées; synthétique réservé aux tests')
            path=ROOT/'runs'/a.experiment;path.mkdir(parents=True,exist_ok=False)
            (path/'history.json').write_text(canonical({'dataset':str(Path(a.dataset).resolve()),'config':cfg,
                'manifest':manifest,'revision':revision(ROOT),'command':f'python -m lab.cli history --config {a.config} --dataset {a.dataset} --experiment {a.experiment}'}))
            print(path)
        elif a.command=='probe':
            from .live import probe
            print(canonical(probe(a.feed,a.seconds,a.output)))
        elif a.command=='live':
            from .live import run_live
            snapshot=run_live(ROOT,a.config,a.metadata,a.feed,a.experiment,a.seconds,a.max_age)
            print(canonical({'health':snapshot['health'],'last_health':snapshot['last_health'],
                             'position_conservée':snapshot['open_position'] is not None}))
        elif a.command=='serve':
            from .server import serve
            serve(ROOT,a.host,a.port)
    except (ValueError,KeyError,FileExistsError,FileNotFoundError) as e:
        p.exit(2,'Erreur : '+str(e)+'\n')

if __name__=='__main__':main()
