"""Points d'entrée normaux sur fixtures explicitement synthétiques; aucune performance de marché."""
import argparse
import csv
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from lab.data import canonical
from tests.test_lab import cfg,spec,bar,m1_fixture,opr_fixture


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    original=m1_fixture();decision=original[459].end
    absent=original[:438];last=absent[-1]
    absent += [bar(i,130,130.5,129.5,130,start=last.end) for i in range(70)]
    unfilled=original[:460]+[bar(i,135,136,134,135,start=decision) for i in range(60)]
    loss=original[:465]+[bar(0,129,130,120,121,start=original[464].end)]
    ambiguous=original[:465]+[bar(0,129,150,120,135,start=original[464].end)]
    cases=[('M1-gain','M1',original,'ENTRY_PENDING'),('M1-loss','M1',loss,'ENTRY_PENDING'),
           ('M1-no-confirmation','M1',absent,'ZONE_TOUCHED'),('M1-unfilled','M1',unfilled,'ENTRY_PENDING'),
           ('M1-ambiguous','M1',ambiguous,'ENTRY_PENDING'),('M5-retest','M5A',opr_fixture(),'ENTRY_PENDING')]
    gap=[bar(i) for i in range(5)]+[bar(5,100,101,99.8,100.8),bar(6,100.8,104,100.7,103.8),
          bar(7,104,106,103,105.8),bar(8,108,109,107,108.5),bar(9,108.5,130,108,120)]
    cases.append(('M5-fvg-gap','M5B',gap,'ENTRY_PENDING'))
    commands=[];results=[]
    def run(command,stem):
        result=subprocess.run(command,text=True,capture_output=True)
        (out/(stem+'.txt')).write_text('COMMAND: '+ ' '.join(command)+'\n'+result.stdout+result.stderr)
        commands.append({'command':command,'exit_code':result.returncode,'log':stem+'.txt'})
        if result.returncode:raise RuntimeError('Commande en échec : '+stem)
        return result.stdout.strip()
    metadata=out/'metadata-test-only.json';metadata.write_text(canonical(spec()))
    for name,family,data,event_kind in cases:
        case=out/name;case.mkdir()
        raw=case/'raw-test-only.csv';config=case/'config-test-only.json';config.write_text(canonical(cfg(family)))
        with raw.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0].record()));writer.writeheader();writer.writerows(b.record() for b in data)
        dataset=run(['python','-m','lab.cli','import-data','--file',str(raw),'--metadata',str(metadata)],name+'-import')
        run(['python','-m','lab.cli','verify-engine','--dataset',dataset,'--config',str(config),
             '--output',str(case/'verification'),'--software-test'],name+'-verify')
        events=[json.loads(x) for x in (case/'verification/events.jsonl').read_text().splitlines()]
        selected=next((e for e in events if e['kind']==event_kind and e['strategy']!='market'),None)
        if selected:
            run(['python','-m','lab.cli','export-decision','--dataset',dataset,'--config',str(config),'--output',str(case/'visual'),
                 '--seq',str(selected['seq']),'--software-test'],name+'-visual')
        tx=json.loads((case/'verification/transactions-software-test-only.json').read_text())['transactions']
        results.append({'case':name,'synthetic':True,'dataset':dataset,'transactions_for_software_test':len(tx),
            'expired_orders':sum(e['kind']=='EXPIRED' for e in events),'visual_event_seq':selected['seq'] if selected else None,
            'ambiguous_events':[e for e in events if e['kind']=='AMBIGUOUS_BAR'],
            'purpose':'Aucune mesure de performance de marché; premiers événements de fixtures indépendantes'})
    (out/'commands.json').write_text(canonical(commands))
    (out/'index.json').write_text(canonical({'synthetic':True,'purpose':'TESTS LOGICIELS UNIQUEMENT','cases':results}))
    print(canonical({'cases':len(results),'all_commands_succeeded':True,'output':str(out),'market_performance_measured':False}))


if __name__=='__main__':main()
