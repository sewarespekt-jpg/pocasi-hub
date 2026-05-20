#!/usr/bin/env python3
import json, os, re
from datetime import datetime, timedelta
import anthropic

# ── KONFIGURACE ──────────────────────────────────────────────────────────────

KINA = [
    {"nazev": "Kino Aero",        "url": "https://www.kinoaero.cz/program"},
    {"nazev": "Kino Atlas",       "url": "https://www.kinoatlaspraha.cz/program"},
    {"nazev": "Bio Oko",          "url": "https://www.biooko.net/program"},
    {"nazev": "Kino Lucerna",     "url": "https://www.kinolucerna.cz/program"},
    {"nazev": "Kino Mat",         "url": "https://www.mat.cz/kino/program"},
    {"nazev": "Kino 35",          "url": "https://kino35.ifp.cz/cz/aktualne"},
    {"nazev": "Kino Světozor",    "url": "https://www.kinosvetozor.cz/program"},
    {"nazev": "Kino Ponrepo",     "url": "https://nfa.cz/cs/kino-ponrepo/program/program"},
    {"nazev": "Edison Filmhub",   "url": "https://www.edisonfilmhub.cz/program"},
    {"nazev": "Kino Pilotů",      "url": "https://kinopilotu.cz/program"},
    {"nazev": "Kino Dlabačov",    "url": "https://www.dlabacov.cz/program"},
]

RPG_RARITY = [
    {"nazev": "LEGENDARY", "barva": "#f97316", "min": 1,  "max": 1},
    {"nazev": "EPIC",      "barva": "#a855f7", "min": 2,  "max": 3},
    {"nazev": "RARE",      "barva": "#22c55e", "min": 4,  "max": 6},
    {"nazev": "UNCOMMON",  "barva": "#38bdf8", "min": 7,  "max": 10},
    {"nazev": "COMMON",    "barva": "#94a3b8", "min": 11, "max": 9999},
]

# ── POMOCNÉ FUNKCE ────────────────────────────────────────────────────────────

def get_rarity(pocet):
    for r in RPG_RARITY:
        if r["min"] <= pocet <= r["max"]:
            return r
    return RPG_RARITY[-1]

def scrape_kino(client, kino, tyden_od, tyden_do):
    """Zavolá Claude s web_search a získá program jednoho kina."""
    print(f"  → {kino['nazev']}...")

    prompt = f"""Jdi na tuto stránku s programem kina: {kino['url']}

Potřebuji seznam filmů které se hrají tento týden ({tyden_od} - {tyden_do}).

Pro každý film spočítej CELKOVÝ POČET PROJEKCÍ za celý týden.
Každý časový slot = jedna projekce. Například film který hraje v pondělí v 18:00 a ve středu v 20:30 má 2 projekce.

DŮLEŽITÉ:
- Nezapočítávej divadelní představení, koncerty ani jiné ne-filmové akce
- Každé samostatné promítání se počítá zvlášť (i stejný film ve více sálech)
- Vrať POUZE validní JSON, žádný jiný text

Odpověz přesně v tomto formátu:
{{
  "filmy": [
    {{"titul": "Název filmu", "pocet_projekci": 3}},
    {{"titul": "Jiný film", "pocet_projekci": 1}}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Vytáhni text z odpovědi
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        # Parsuj JSON
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            print(f"    ✗ Žádný JSON v odpovědi")
            return []

        data = json.loads(json_match.group())
        filmy = data.get("filmy", [])
        print(f"    ✓ {len(filmy)} filmů")
        return filmy

    except json.JSONDecodeError as e:
        print(f"    ✗ Chyba parsování JSON: {e}")
        return []
    except Exception as e:
        print(f"    ✗ Chyba: {e}")
        return []

# ── HLAVNÍ LOGIKA ─────────────────────────────────────────────────────────────

def main():
    dnes = datetime.now()
    tyden_od = dnes.strftime("%d.%m.")
    tyden_do = (dnes + timedelta(days=6)).strftime("%d.%m.%Y")

    print(f"\n🎬 Kino scraper (Claude API): {dnes.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Týden: {tyden_od} - {tyden_do}\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("CHYBA: ANTHROPIC_API_KEY není nastaven!")
        exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Agreguj filmy napříč všemi kiny
    # {"Název filmu": celkový počet projekcí}
    film_agregat = {}

    for kino in KINA:
        filmy = scrape_kino(client, kino, tyden_od, tyden_do)
        for film in filmy:
            titul = film.get("titul", "").strip()
            pocet = int(film.get("pocet_projekci", 1))
            if not titul or len(titul) < 2:
                continue
            # Normalizuj název (odstraň extra mezery)
            titul = re.sub(r'\s+', ' ', titul)
            if titul in film_agregat:
                film_agregat[titul] += pocet
            else:
                film_agregat[titul] = pocet

    print(f"\n📊 Celkem unikátních filmů: {len(film_agregat)}")

    # Seřaď: nejméně projekcí = nejvíc exkluzivní = nahoře
    filmy_sorted = sorted(film_agregat.items(), key=lambda x: x[1])

    # Přidej RPG raritu
    filmy_final = []
    for titul, pocet in filmy_sorted:
        rarita = get_rarity(pocet)
        filmy_final.append({
            "titul": titul,
            "pocet_projekci": pocet,
            "rarita": rarita["nazev"],
            "barva": rarita["barva"]
        })

    # Ulož kina.json
    out = {
        "aktualizovano": dnes.strftime("%Y-%m-%d %H:%M"),
        "tyden": f"{tyden_od} - {tyden_do}",
        "filmy": filmy_final
    }

    with open("kina.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✅ Hotovo! {len(filmy_final)} filmů → kina.json\n")

    # Výpis prvních 10 pro kontrolu
    print("Top 10 nejexkluzivnějších filmů:")
    for film in filmy_final[:10]:
        print(f"  [{film['rarita']:10}] {film['titul']} ({film['pocet_projekci']}x)")

if __name__ == "__main__":
    main()
