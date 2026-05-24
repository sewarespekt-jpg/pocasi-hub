#!/usr/bin/env python3
import json, os, re
from datetime import datetime, timedelta
import anthropic

KINA = [
    {"nazev": "Kino Aero",      "url": "https://www.kinoaero.cz/program"},
    {"nazev": "Kino Atlas",     "url": "https://www.kinoatlaspraha.cz/program"},
    {"nazev": "Bio Oko",        "url": "https://www.biooko.net/program"},
    {"nazev": "Kino Lucerna",   "url": "https://www.kinolucerna.cz/program"},
    {"nazev": "Kino Mat",       "url": "https://www.mat.cz/kino/program"},
    {"nazev": "Kino 35",        "url": "https://kino35.ifp.cz/cz/aktualne"},
    {"nazev": "Kino Světozor",  "url": "https://www.kinosvetozor.cz/program"},
    {"nazev": "Kino Ponrepo",   "url": "https://nfa.cz/cs/kino-ponrepo/program/program"},
    {"nazev": "Edison Filmhub", "url": "https://www.edisonfilmhub.cz/program"},
    {"nazev": "Kino Pilotů",    "url": "https://kinopilotu.cz/program"},
    {"nazev": "Kino Dlabačov",  "url": "https://www.dlabacov.cz/program"},
]

RPG = [
    {"nazev": "LEGENDARY", "barva": "#f97316", "min": 1,  "max": 1},
    {"nazev": "EPIC",      "barva": "#a855f7", "min": 2,  "max": 3},
    {"nazev": "RARE",      "barva": "#22c55e", "min": 4,  "max": 6},
    {"nazev": "UNCOMMON",  "barva": "#38bdf8", "min": 7,  "max": 10},
    {"nazev": "COMMON",    "barva": "#94a3b8", "min": 11, "max": 9999},
]

def get_rarity(n):
    for r in RPG:
        if r["min"] <= n <= r["max"]:
            return r
    return RPG[-1]

def main():
    dnes = datetime.now()
    tyden_od = dnes.strftime("%d.%m.")
    tyden_do = (dnes + timedelta(days=7)).strftime("%d.%m.%Y")

    print(f"Kino scraper (Haiku + 1 call): {dnes.strftime('%Y-%m-%d %H:%M')}")
    print(f"Týden: {tyden_od} - {tyden_do}\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("CHYBA: ANTHROPIC_API_KEY není nastaven!")
        exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    kina_seznam = "\n".join([f"- {k['nazev']}: {k['url']}" for k in KINA])

    prompt = f"""Jsi asistent který sbírá program pražských kin.

Projdi weby těchto kin a zjisti jejich program na týden {tyden_od} - {tyden_do}:

{kina_seznam}

Pro každý film spočítej CELKOVÝ POČET PROJEKCÍ napříč VŠEMI kiny za celý týden.
Každý časový slot = 1 projekce. Film hrající ve dvou kinech po 3× = 6 projekcí celkem.

Pravidla:
- Ignoruj dokumenty, koncerty, divadlo - jen filmy
- Ignoruj Cinema City, CineStar - to jsou multiplexy
- Každé samostatné promítání = +1

Vrať POUZE validní JSON, nic jiného:
{{
  "filmy": [
    {{"titul": "Název filmu", "pocet_projekci": 3}},
    {{"titul": "Jiný film", "pocet_projekci": 1}}
  ]
}}"""

    print("Volám Claude Haiku API (1 call)...")
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        print(f"Tokeny: vstup={response.usage.input_tokens}, výstup={response.usage.output_tokens}")

        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            print("CHYBA: Žádný JSON v odpovědi")
            print("Odpověď:", text[:500])
            exit(1)

        data = json.loads(json_match.group())
        filmy_raw = data.get("filmy", [])

        filmy_sorted = sorted(filmy_raw, key=lambda x: x.get("pocet_projekci", 1))
        filmy_final = []
        for film in filmy_sorted:
            titul = film.get("titul", "").strip()
            pocet = int(film.get("pocet_projekci", 1))
            if not titul:
                continue
            rarita = get_rarity(pocet)
            filmy_final.append({
                "titul": titul,
                "pocet_projekci": pocet,
                "rarita": rarita["nazev"],
                "barva": rarita["barva"]
            })

        out = {
            "aktualizovano": dnes.strftime("%Y-%m-%d %H:%M"),
            "tyden": f"{tyden_od} - {tyden_do}",
            "filmy": filmy_final
        }

        with open("kina.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"\nHotovo! {len(filmy_final)} filmů → kina.json")
        for f in filmy_final[:10]:
            print(f"  [{f['rarita']:10}] {f['titul']} ({f['pocet_projekci']}×)")

    except json.JSONDecodeError as e:
        print(f"CHYBA parsování JSON: {e}")
        exit(1)
    except Exception as e:
        print(f"CHYBA: {e}")
        exit(1)

if __name__ == "__main__":
    main()
