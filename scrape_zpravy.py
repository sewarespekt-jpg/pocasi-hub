#!/usr/bin/env python3
import json, os, re
from datetime import datetime
import anthropic

PROMPT = """<ucel_projektu>
Denní mediální screening dvou zemí: Německo a Česko.
</ucel_projektu>

<co_presne_delas>
Pro každou ze dvou zemí najdi TOP 3 TÉMATA, kterými ta země v daný den skutečně žije.
Téma může být cokoli – politika, ekonomika, sport, kultura, kauza, tragédie, skandál, společenská debata.
Kritérium je jediné: je to skutečně to, o čem se ve veřejném prostoru v té zemi mluví.

Každé téma zpracuj tak, aby čtenář pochopil KONTEXT, ne jen holý fakt:
* Co se stalo (fakt)
* Proč to je velké téma zrovna teď (pozadí, předhistorie)
* Co to znamená dál (důsledky, co sledovat)
* Hlavní aktéři a jejich případná politická příslušnost
</co_presne_delas>

<vyhledavani>
Proveď PŘESNĚ 5 vyhledávání — ne méně, ne více.
Rozdělení:
- 2 vyhledávání pro Německo (v němčině: "Schlagzeilen heute", "wichtigste Nachrichten heute Deutschland")
- 2 vyhledávání pro Česko (v češtině: "hlavní zprávy dnes Česko", "nejdůležitější zprávy dnes")
- 1 vyhledávání pro téma dne které nejvíc rezonuje ve veřejném prostoru ("co se dnes řeší Česko", "was bewegt Deutschland heute")
</vyhledavani>

<zdroje>
Německo: tagesschau.de, spiegel.de, sueddeutsche.de, faz.net, zeit.de
Česko: novinky.cz, idnes.cz, aktualne.cz, irozhlas.cz, denikn.cz
Preferuj tyto zdroje ale nevylučuj jiné pokud přinesou relevantní informaci.
</zdroje>

<vystup>
Veškerý výstup piš VÝHRADNĚ V ČEŠTINĚ.
Délka zpracování každé země: maximálně na minutu čtení.
DŮLEŽITÉ: Vrať POUZE čistý validní JSON bez jakýchkoliv HTML tagů, cite tagů nebo markdown formátování.

Vrať POUZE validní JSON, žádný jiný text:
{
  "datum": "DD.MM.YYYY",
  "zeme": [
    {
      "nazev": "Německo",
      "emoji": "DE",
      "hlavni_tema": "Jedna věta co nejvíc hýbe zemí dnes",
      "temata": [
        {
          "nazev": "Název tématu",
          "co_se_stalo": "Fakt co přesně se stalo",
          "proc_je_to_dulezite": "Pozadí a předhistorie",
          "co_sledovat": "Důsledky a co sledovat dál",
          "akteri": "Hlavní aktéři a jejich případná politická příslušnost",
          "zdroj": "Médium ze kterého fakta pocházejí"
        }
      ]
    },
    {
      "nazev": "Česko",
      "emoji": "CZ",
      "hlavni_tema": "Jedna věta co nejvíc hýbe zemí dnes",
      "temata": [
        {
          "nazev": "Název tématu",
          "co_se_stalo": "Fakt co přesně se stalo",
          "proc_je_to_dulezite": "Pozadí a předhistorie",
          "co_sledovat": "Důsledky a co sledovat dál",
          "akteri": "Hlavní aktéři a jejich případná politická příslušnost",
          "zdroj": "Médium ze kterého fakta pocházejí"
        }
      ]
    }
  ]
}
</vystup>

<dulezite>
* Pokud něco nevíš jistě, použij fráze "zdá se", "média poukazují na", "komentátoři se shodují"
* Neuváděj čísla, data, jména nebo citace které nejsou podložené nalezeným zdrojem
* Rozlišuj fakt od interpretace
* Pokud se zdroje rozcházejí, uveď to
* Radši méně informací ale ověřených, než více vycucaných z palce
* JSON musí být kompletní a validní — nekrát ho uprostřed
</dulezite>"""


def clean_text(text):
    """Odstraní citation tagy a HTML ze stringů."""
    if not isinstance(text, str):
        return text
    text = re.sub(r']*>(.*?)', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def clean_data(obj):
    """Rekurzivně vyčistí všechny stringy v datech."""
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(i) for i in obj]
    elif isinstance(obj, str):
        return clean_text(obj)
    return obj


def main():
    dnes = datetime.now()
    print(f"Zpravy scraper (Haiku): {dnes.strftime('%Y-%m-%d %H:%M')}\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("CHYBA: ANTHROPIC_API_KEY není nastaven!")
        exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("Volám Claude Haiku API...")
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": PROMPT}]
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        print(f"Tokeny: vstup={response.usage.input_tokens}, výstup={response.usage.output_tokens}")

        # Nejdřív vyčisti cite tagy z raw textu PŘED parsováním JSON
        text = re.sub(r']*>(.*?)', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)

        # Najdi JSON v odpovědi
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            print("CHYBA: Žádný JSON v odpovědi")
            print("Odpověď:", text[:500])
            exit(1)

        json_str = json_match.group()

        # Zkus parsovat JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON chyba na pozici {e.pos}: {e.msg}")
            # Zkus najít jen validní část
            try:
                # Ořízni na konec posledního kompletního objektu zemí
                truncated = json_str[:e.pos]
                last_brace = truncated.rfind('}}')
                if last_brace > 0:
                    fixed = truncated[:last_brace + 2] + ']}' 
                    data = json.loads(fixed)
                    print("JSON opraven zkrácením.")
                else:
                    print("CHYBA: JSON nelze opravit")
                    print("Text kolem chyby:", json_str[max(0, e.pos-200):e.pos+200])
                    exit(1)
            except Exception as e2:
                print(f"CHYBA opravy JSON: {e2}")
                exit(1)

        # Vyčisti cite tagy a HTML
        data = clean_data(data)
        data["aktualizovano"] = dnes.strftime("%Y-%m-%d %H:%M")

        with open("zpravy.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\nHotovo! zpravy.json uložen.")
        for zeme in data.get("zeme", []):
            print(f"\n{zeme.get('nazev', '?')}: {zeme.get('hlavni_tema', '?')}")
            for t in zeme.get("temata", []):
                print(f"  - {t.get('nazev', '?')}")

    except json.JSONDecodeError as e:
        print(f"CHYBA parsování JSON: {e}")
        exit(1)
    except Exception as e:
        print(f"CHYBA: {e}")
        exit(1)


if __name__ == "__main__":
    main()
