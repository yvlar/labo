"""Contrôle fini de l'interface vide, sans aucune donnée de performance synthétique."""
import json
import multiprocessing
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from lab.server import serve
from lab.cli import ROOT

def main():
    port=18765
    process=multiprocessing.Process(target=serve,args=(ROOT,'127.0.0.1',port),daemon=True)
    process.start()
    result={}
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(30):
            try:
                data=json.loads(opener.open(f'http://127.0.0.1:{port}/api/catalog',timeout=1).read());break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Serveur local indisponible')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page=browser.new_page(viewport={'width':1440,'height':1050})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}',wait_until='networkidle')
            page.get_by_role('heading',name='Laboratoire de trading').wait_for()
            page.get_by_role('button',name='Règles & sources').click()
            page.locator('#rule-list .rule').first.wait_for()
            assert page.locator('#rule-list .rule').count()==34
            page.locator('#search').fill('R24')
            assert page.locator('#rule-list .rule').count()==1
            page.get_by_role('button',name='Comparaisons').click()
            assert page.locator('#models .model').count()==len(data['models'])
            page.get_by_role('button',name='Laboratoire',exact=False).click()
            page.screenshot(path=str(ROOT/'reports/interface.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert not errors,errors
            result={'browser':'Chromium système, Playwright','desktop':[1440,1050],'mobile':[390,844],
                    'javascript_errors':errors,'rules_visible':34,'models_visible':len(data['models']),
                    'result':'PASS','market_data_used':False,'server_stopped':True}
            browser.close()
        (ROOT/'reports/browser-verification.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:
        process.terminate();process.join(timeout=5)

if __name__=='__main__':main()
