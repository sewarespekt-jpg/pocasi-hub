#!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timedelta
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright neni nainstalovan."); sys.exit(1)

DAYS_MAP = {0:'Po',1:'Ut',2:'St',3:'Ct',4:'Pa',5:'So',6:'Ne'}
DAYS_ORDER = ['Po','Ut','St','Ct','Pa','So','Ne']
SKIP = ['kino','cinema','sold out','running','rezervace','vstupenky','loading','cookie',' kc','http','www.','aero','bio oko','svetozor','lucerna','pritomnost','scala','senior','eng ']

def clean(t): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',t)).strip()
def sort_days(d): return sorted(d, key=lambda x: DAYS_ORDER.index(x) if x in DAYS_ORDER else 99)

def parse_html(html):
    filmy = {}
    sections = re.split(r'(?=id="program-day-\d{4}-\d{2}-\d{2}")', html)
    for section in sections:
        dm = re.search(r'program-day-(\d{4})-(\d{2})-(\d{2})', section)
        if not dm: continue
        try:
            dt = datetime(int(dm.group(1)),int(dm.group(2)),int(dm.group(3)))
            day = DAYS_MAP[dt.weekday()]
        except: continue
        for m in re.finditer(r'(\d{2}:\d{2})[^<]{0,100}?<[^>]+>\s*([A-Z\xc1\xc4\xc9\xcd\xd3\xda\xdd\xc6\xd0\xd1\xd8\xde][^<\n]{4,80})', section):
            cas = m.group(1)
            titul = clean(m.group(2))
            if not (4 < len(titul) < 80): continue
            if any(w in titul.lower() for w in SKIP): continue
            if titul not in filmy: filmy[titul] = {'dny':set(),'casy':set()}
            filmy[titul]['dny'].add(day)
            filmy[titul]['casy'].add(cas)
    result = [{'titul':t,'dny':sort_days(list(d['dny'])),'casy':sorted(d['casy']),'poznamka':''} for t,d in filmy.items()]
    result.sort(key=lambda f: DAYS_ORDER.index(f['dny'][0]) if f['dny'] else 99)
    return result[:12]

KINA = [
    {'nazev':'Kino Aero',     'url':'https://www.kinoaero.cz/'},
    {'nazev':'Bio Oko',       'url':'https://www.biooko.net/'},
    {'nazev':'Svetozor',      'url':'https://kinosvetozor.cz/'},
    {'nazev':'Lucerna',       'url':'https://www.kinolucerna.cz/'},
    {'nazev':'Kino Mat',      'url':'https://www.mat.cz/kino/'},
    {'nazev':'Edison Filmhub','url':'https://www.edisonfilmhub.cz/program'},
]

def main():
    print(f"\nKino scraper: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-setuid-sandbox'])
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
            viewport={'width':1280,'height':800}, locale='cs-CZ'
        )
        for kino in KINA:
            print(f"  -> {kino['nazev']}...")
            page = ctx.new_page()
            try:
                page.goto(kino['url'], wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                filmy = parse_html(page.content())
                print(f"  OK {len(filmy)} filmu")
                results.append({'nazev':kino['nazev'],'url':kino['url'],'filmy':filmy})
            except Exception as e:
                print(f"  CHYBA {e}")
                results.append({'nazev':kino['nazev'],'url':kino['url'],'filmy':[],'chyba':str(e)})
            finally:
                page.close()
        browser.close()
    out = {
        'aktualizovano': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'tyden': f"{datetime.now().strftime('%d.%m.')} - {(datetime.now()+timedelta(days=6)).strftime('%d.%m.%Y')}",
        'kina': results
    }
    with open('kina.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    total = sum(len(k.get('filmy',[])) for k in results)
    print(f"\nHotovo! {total} filmu -> kina.json\n")

if __name__ == '__main__':
    main()
