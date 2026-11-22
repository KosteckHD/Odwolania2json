"""Zestaw „inny układ”: odwołania z danych UZP przepisane w innym układzie i innymi sformułowaniami.

Wszystkie dokumenty UZP pochodzą z jednego generatora (stałe etykiety, np. „adres do korespondencji:”,
„Zamawiający w dniu …”). Ten skrypt bierze wzorcowy JSON odwołania (dane się nie zmieniają) oraz kilka
fragmentów oryginalnego PDF (lista pełnomocników, tryb, zarzuty) i składa nowy PDF w jednym z kilku
układów: inne etykiety (Pełnomocnik:, Adres do doręczeń, Działający przez), inna kolejność sekcji,
kancelaria w papierze firmowym, stopce albo przy podpisie, data i miejscowość w innym miejscu, inaczej
sformułowana zaskarżona czynność, konsorcjum z liderem opisanym inaczej.

Wynik: <out>/dane/wariant_NN/odwolanie.{pdf,json} oraz <out>/manifest.json (split „test”, żeby nie
mieszać z wejściem development/validation w .local/experiments). Pomiar:
    python evaluation/experiment.py --split test --manifest <out>/manifest.json --data <out>/dane ...
(przed pierwszym przebiegiem usuń .local/experiments/_input-test, jeśli powstał z innego manifestu).

    python evaluation/layout_variants.py --data C:/.../uzp-repo/dane --out .local/layout
"""
import argparse
import json
import re
import shutil
import textwrap
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

# Przypadki z podziału development: różne powody, jeden i dwóch zamawiających, konsorcjum, brak daty pisma.
CASES = (2, 3, 5, 6, 8, 9, 11, 15, 16, 19, 22, 25, 33, 41, 42)

MONTHS = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
          "października", "listopada", "grudnia")
LOCATIVE = {"Gdańsk": "Gdańsku", "Bydgoszcz": "Bydgoszczy", "Katowice": "Katowicach", "Lublin": "Lublinie",
            "Warszawa": "Warszawie", "Rzeszów": "Rzeszowie", "Kraków": "Krakowie", "Poznań": "Poznaniu",
            "Wrocław": "Wrocławiu", "Łódź": "Łodzi"}

# Zaskarżona czynność: (rzeczownik odczasownikowy po „polegającej na”, zdanie z czasownikiem).
ACTS = {
    1: ("odrzuceniu oferty Odwołującego", "odrzucił ofertę złożoną przez Odwołującego"),
    2: ("wyborze jako najkorzystniejszej oferty innego wykonawcy", "dokonał wyboru oferty najkorzystniejszej"),
    3: ("wykluczeniu Odwołującego z postępowania", "wykluczył Odwołującego z postępowania"),
    4: ("ustaleniu treści ogłoszenia o zamówieniu i Specyfikacji Warunków Zamówienia",
        "opublikował ogłoszenie o zamówieniu wraz ze Specyfikacją Warunków Zamówienia"),
    5: ("zmianie treści Specyfikacji Warunków Zamówienia", "zmodyfikował treść Specyfikacji Warunków Zamówienia"),
    6: ("udzieleniu wyjaśnień treści SWZ w odpowiedzi na pytania wykonawców",
        "udzielił odpowiedzi na pytania wykonawców dotyczące treści SWZ"),
    7: ("zaniechaniu odrzucenia oferty wykonawcy, który złożył ofertę niezgodną z warunkami zamówienia",
        "zaniechał odrzucenia oferty konkurencyjnego wykonawcy"),
    8: ("zaniechaniu wykluczenia z postępowania wykonawcy podlegającego wykluczeniu",
        "zaniechał wykluczenia wykonawcy, który nie wykazał braku podstaw wykluczenia"),
    9: ("unieważnieniu postępowania o udzielenie zamówienia", "unieważnił postępowanie o udzielenie zamówienia"),
    10: ("zaniechaniu unieważnienia postępowania obarczonego niemożliwą do usunięcia wadą",
         "zaniechał unieważnienia postępowania, mimo że jest ono obarczone wadą"),
    11: ("sporządzeniu opisu przedmiotu zamówienia w sposób utrudniający uczciwą konkurencję",
         "udostępnił opis przedmiotu zamówienia zawierający wymagania ograniczające konkurencję"),
    12: ("ukształtowaniu projektowanych postanowień umowy w sposób nadmiernie obciążający wykonawcę",
         "udostępnił projektowane postanowienia umowy rażąco naruszające równowagę stron"),
}

PARTNER = ("Velmar Technika sp. z o.o.", "ul. Fabryczna 12, 41-200 Sosnowiec",
           "KRS: 9990001112, NIP: 9990002223, REGON: 999000334")


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def words_date(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{int(day)} {MONTHS[int(month) - 1]} {year} r."


def dotted_date(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{day}.{month}.{year} r."


def source_facts(text: str) -> dict:
    flat = re.sub(r"\s+", " ", re.sub(r"Strona \d+ z \d+", " ", text))
    people = re.search(r"reprezentowan\w*\s+przez:?\s*(.+)", text)
    attorneys = []
    for chunk in (people.group(1).split(",") if people else ()):
        match = re.match(r"\s*((?:adw\.|r\.\s*pr\.|radca prawny|adwokat)?)\s*(.+?)\s*$", chunk)
        if match:
            attorneys.append(((match.group(1) or "adw.").replace("r. pr.", "r. pr."), match.group(2)))
    mode = re.search(r"trybie\s+(.+?)\s+pn\.", flat)
    claims = re.search(r"(Zarzut nr 1.+?)(?:W związku z powyższym wnoszę|Wnoszę o:|Wnosz[ęe] o\b)", flat)
    claim_text = claims.group(1) if claims else "Zarzut nr 1 naruszenia art. 16 Pzp przez prowadzenie postępowania w sposób nieprzejrzysty."
    return {"attorneys": attorneys, "mode": mode.group(1) if mode else "przetargu nieograniczonego",
            "claims": claim_text[:2600]}


def identifiers(entity: dict, order=("nip", "regon", "krs")) -> str:
    labels = {"krs": "KRS", "nip": "NIP", "regon": "REGON"}
    return ", ".join(f"{labels[key]} {entity[key]}" for key in order if entity.get(key))


def proceeding(gold: dict, facts: dict) -> list[str]:
    zp = gold["ZamowieniePubliczne"]
    lines = [f"Nazwa zamówienia: „{zp['tytul']}” (tryb {facts['mode']})"]
    if zp.get("numer_postepowania"):
        lines.append(f"Znak sprawy nadany przez Zamawiającego: {zp['numer_postepowania']}")
    if zp.get("numer_bzp"):
        lines.append(f"Ogłoszenie opublikowane w Biuletynie Zamówień Publicznych pod nr {zp['numer_bzp'].replace('BZP', 'BZP ')}")
    if zp.get("numer_ted"):
        number, year = zp["numer_ted"].split("-")
        lines.append(f"Ogłoszenie w Dz. Urz. UE: {year}/S 000-{number}")
    return lines


def buyers(gold: dict, label: str) -> list[str]:
    items = gold["Zamawiajacy"]
    if len(items) == 1:
        z = items[0]
        return [label, z["nazwa"], "ul. Urzędowa 3, 00-950 Warszawa", identifiers(z, ("regon", "nip", "krs")),
                "e-mail: zamowienia@zamawiajacy.example"]
    lines = [label + " (zamówienie wspólne)"]
    for index, z in enumerate(items, 1):
        role = "– działający w imieniu wszystkich zamawiających (prowadzi postępowanie)" if z.get("prowadzacy_postepowanie") else "– zamawiający wspólnie"
        lines += [f"{index}. {z['nazwa']} {role}", identifiers(z, ("regon", "nip", "krs"))]
    return lines


def attorneys_text(facts: dict, gold_person: str, joiner=" oraz ") -> str:
    people = facts["attorneys"] or [("adw.", gold_person)]
    return joiner.join(f"{title} {name}" for title, name in people)


def signature(facts: dict, gold_person: str) -> list[str]:
    title, name = (facts["attorneys"] or [("adw.", gold_person)])[0]
    return ["", "Z poważaniem,", f"{title} {name}", "(podpisano kwalifikowanym podpisem elektronicznym)"]


def layout(variant: int, gold: dict, facts: dict) -> tuple[list[str], str | None]:
    """Zwraca (wiersze dokumentu, stopka powtarzana na każdej stronie)."""
    k, o = gold["OdwolanieKIO"], gold["Odwolujacy"][0]
    p = o["pelnomocnik"]
    noun, verb = ACTS[k["czynnosc_powod_id"]]
    city, date = k.get("miejscowosc"), k.get("data")
    act_day = k["czynnosc_dzien"]
    claims = facts["claims"]
    place_date_top = [f"{city}, {dotted_date(date)}"] if date and city else []
    footer = None

    if variant == 0:  # etykiety „Pełnomocnik:” i „Adres do doręczeń”, czynność w zdaniu „wobec czynności z dnia”
        lines = [*place_date_top, "", "Do Prezesa Krajowej Izby Odwoławczej", "ul. Postępu 17a, 02-676 Warszawa", "",
                 "ODWOŁANIE", "", "Wykonawca wnoszący odwołanie:", o["nazwa"], "ul. Nadrzeczna 7, 00-001 Warszawa",
                 identifiers(o), f"Pełnomocnik: {attorneys_text(facts, p['imie_nazwisko'])}",
                 f"Adres do doręczeń: {p['nazwa']}, ul. Lipowa 4 lok. 2, 00-002 Warszawa, e-mail: {p['mail']}", "",
                 *buyers(gold, "Zamawiający:"), "", *proceeding(gold, facts), "",
                 f"Odwołanie wnoszę wobec czynności Zamawiającego z dnia {dotted_date(act_day)}, polegającej na {noun}.",
                 "", claims, *signature(facts, p["imie_nazwisko"])]
    elif variant == 1:  # zamawiający pierwszy, „Działający przez”, kancelaria tylko przy podpisie, data na końcu
        title, name = (facts["attorneys"] or [("adw.", p["imie_nazwisko"])])[0]
        lines = ["Krajowa Izba Odwoławcza", "ul. Postępu 17a", "02-676 Warszawa", "",
                 *buyers(gold, "Zamawiający:"), "", "Odwołujący:", o["nazwa"], identifiers(o, ("krs", "regon", "nip")),
                 f"e-mail Odwołującego: sekretariat@odwolujacy.example",
                 f"Działający przez: {attorneys_text(facts, p['imie_nazwisko'], ', ')} (pełnomocnictwo w załączeniu)",
                 "", "ODWOŁANIE od czynności Zamawiającego", "", *proceeding(gold, facts), "",
                 f"Dnia {words_date(act_day)} Zamawiający {verb}. Odwołujący nie zgadza się z tą czynnością.",
                 "", claims, ""]
        if date and city:
            lines.append(f"{city}, dnia {words_date(date)}")
        lines += ["", f"{title} {name}", p["nazwa"], "ul. Ogrodowa 15, 00-003 Warszawa", f"e-mail: {p['mail']}"]
    elif variant == 2:  # konsorcjum opisane inaczej, kancelaria w stopce, czynność „przedmiotem zaskarżenia jest”
        lines = [*([f"{city}, dnia {words_date(date)}"] if date and city else []), "",
                 "Krajowa Izba Odwoławcza przy Prezesie Urzędu Zamówień Publicznych", "", "ODWOŁANIE", "",
                 "Odwołujący – wykonawcy wspólnie ubiegający się o udzielenie zamówienia:",
                 f"a) {o['nazwa']} – pełnomocnik pozostałych wykonawców (lider konsorcjum),",
                 "   ul. Nadrzeczna 7, 00-001 Warszawa, " + identifiers(o),
                 f"b) {PARTNER[0]}, {PARTNER[1]}, {PARTNER[2]}",
                 f"Działający przez: {attorneys_text(facts, p['imie_nazwisko'])}", "",
                 *buyers(gold, "Zamawiający:"), "", *proceeding(gold, facts), "",
                 f"Przedmiotem zaskarżenia jest czynność Zamawiającego polegająca na {noun}, "
                 f"o której Odwołujący dowiedział się w dniu {act_day}.", "", claims,
                 *signature(facts, p["imie_nazwisko"])]
        footer = f"{p['nazwa']} | ul. Kwiatowa 9, 00-004 Warszawa | tel. 22 000 00 00 | {p['mail']}"
    elif variant == 3:  # papier firmowy kancelarii na górze, pełnomocnik w zdaniu
        lines = [p["nazwa"], "ul. Polna 22, 00-005 Warszawa", f"tel. 22 111 11 11 | {p['mail']}", "",
                 *place_date_top, "", "Prezes Krajowej Izby Odwoławczej", "ul. Postępu 17a, 02-676 Warszawa", "",
                 f"Odwołujący: {o['nazwa']}, ul. Nadrzeczna 7, 00-001 Warszawa ({identifiers(o)})",
                 f"W imieniu Odwołującego działa pełnomocnik: {attorneys_text(facts, p['imie_nazwisko'])}", "",
                 *buyers(gold, "Zamawiający:"), "", "ODWOŁANIE", "", *proceeding(gold, facts), "",
                 f"Niniejsze odwołanie dotyczy czynności Zamawiającego dokonanej {dotted_date(act_day)} i polegającej na {noun}.",
                 "", claims, *signature(facts, p["imie_nazwisko"])]
    elif variant == 5:  # konsorcjum: partner wymieniony pierwszy, lider drugi; kancelaria w nagłówku pisma
        lines = [f"{p['nazwa']} – {p['mail']}", *place_date_top, "", "Krajowa Izba Odwoławcza", "",
                 "Odwołujący (konsorcjum):",
                 f"1) {PARTNER[0]} – członek konsorcjum, {PARTNER[1]}, {PARTNER[2]}",
                 f"2) {o['nazwa']} – lider konsorcjum, ul. Nadrzeczna 7, 00-001 Warszawa, {identifiers(o, ('krs', 'nip', 'regon'))}",
                 f"reprezentowani przez pełnomocnika: {attorneys_text(facts, p['imie_nazwisko'], ', ')}", "",
                 *buyers(gold, "Zamawiający:"), "", "ODWOŁANIE", "", *proceeding(gold, facts), "",
                 f"Odwołanie dotyczy czynności Zamawiającego polegającej na {noun} (zawiadomienie z dnia {words_date(act_day)}).",
                 "", claims, *signature(facts, p["imie_nazwisko"])]
    elif variant == 6:  # nagłówek w dwóch kolumnach (odwołujący | zamawiający) sklejony wierszami jak po ekstrakcji
        left = ["Odwołujący:", o["nazwa"], "ul. Nadrzeczna 7, 00-001 Warszawa", identifiers(o),
                f"Pełnomocnik: {attorneys_text(facts, p['imie_nazwisko'], ', ')}", p["nazwa"], p["mail"]]
        right = buyers(gold, "Zamawiający:")
        width = max(len(line) for line in left) + 4
        rows = [f"{a:<{width}}{b}" for a, b in zip(left + [""] * len(right), right + [""] * len(left))]
        rows = [row.rstrip() for row in rows if row.strip()]
        lines = [*place_date_top, "Prezes Krajowej Izby Odwoławczej, ul. Postępu 17a, 02-676 Warszawa", "", *rows, "",
                 "ODWOŁANIE", "", *proceeding(gold, facts), "",
                 f"Zaskarżona czynność polega na {noun} – data czynności: {dotted_date(act_day)}", "", claims,
                 *signature(facts, p["imie_nazwisko"])]
    else:  # dane stron w akapicie, kancelaria w zdaniu otwierającym, data i miejscowość w odmianie na końcu
        title, name = (facts["attorneys"] or [("adw.", p["imie_nazwisko"])])[0]
        lines = ["Krajowa Izba Odwoławcza", "", "ODWOŁANIE", "",
                 f"Działając jako pełnomocnik wykonawcy {o['nazwa']} z siedzibą w Warszawie ({identifiers(o)}), "
                 f"dalej „Odwołujący”, ja, {title} {name} z kancelarii {p['nazwa']} (adres do doręczeń elektronicznych: {p['mail']}), "
                 "wnoszę odwołanie w postępowaniu prowadzonym przez:", *buyers(gold, "Zamawiający:")[1:], "",
                 *proceeding(gold, facts), "",
                 f"Zaskarżam następującą czynność: Zamawiający {verb} – informację o tym przekazano Odwołującemu {words_date(act_day)}",
                 "", claims, ""]
        if date and city:
            lines.append(f"Sporządzono w {LOCATIVE.get(city, city)} dnia {words_date(date)}")
        lines += signature(facts, p["imie_nazwisko"])
    return lines, footer


# --- PDF z polskimi znakami: Helvetica z kodowaniem WinAnsi i tablicą /Differences ---
EXTRA_GLYPHS = {"Ą": "Aogonek", "ą": "aogonek", "Ć": "Cacute", "ć": "cacute", "Ę": "Eogonek", "ę": "eogonek",
                "Ł": "Lslash", "ł": "lslash", "Ń": "Nacute", "ń": "nacute", "Ś": "Sacute", "ś": "sacute",
                "Ź": "Zacute", "ź": "zacute", "Ż": "Zdotaccent", "ż": "zdotaccent"}
FREE_CODES = (0x81, 0x8D, 0x8F, 0x90, 0x9D, 0xA0, 0xAD, 0xA4, 0xA6, 0xA8, 0xAA, 0xAF, 0xB4, 0xB8, 0xBA, 0xBC)
CODE = {char: code for char, code in zip(EXTRA_GLYPHS, FREE_CODES)}


def encode(line: str) -> str:
    out = []
    for char in line:
        if char in CODE:
            out.append(f"\\{CODE[char]:03o}")
            continue
        try:
            byte = char.encode("cp1252")
        except UnicodeEncodeError:
            byte = b"?"
        for value in byte:
            ch = chr(value)
            out.append("\\" + ch if ch in "()\\" else ch if 32 <= value < 127 else f"\\{value:03o}")
    return "".join(out)


def font() -> DictionaryObject:
    differences = ArrayObject()
    for char, code in CODE.items():
        differences += [NumberObject(code), NameObject("/" + EXTRA_GLYPHS[char])]
    n = NameObject
    return DictionaryObject({n("/Type"): n("/Font"), n("/Subtype"): n("/Type1"), n("/BaseFont"): n("/Helvetica"),
                             n("/Encoding"): DictionaryObject({n("/Type"): n("/Encoding"),
                                                               n("/BaseEncoding"): n("/WinAnsiEncoding"),
                                                               n("/Differences"): differences})})


def write_pdf(path: Path, lines: list[str], footer: str | None, per_page: int = 52) -> None:
    wrapped = []
    for line in lines:
        # wiersze dwukolumnowe (wiele spacji) zostają w całości, jak w PDF ze składem w kolumnach
        wrapped += ([line] if "    " in line else textwrap.wrap(line, 92)) or [""]
    pages = [wrapped[i:i + per_page] for i in range(0, len(wrapped), per_page)] or [[]]
    with PdfWriter() as writer:
        f1 = font()
        for number, chunk in enumerate(pages, 1):
            page = writer.add_blank_page(width=595, height=842)
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): f1})})
            body = "\n".join(f"({encode(line)}) Tj T*" for line in chunk)
            tail = f"\nBT /F1 8 Tf 40 30 Td ({encode(footer)}) Tj ET" if footer else ""
            tail += f"\nBT /F1 8 Tf 500 18 Td ({encode(f'str. {number}/{len(pages)}')}) Tj ET"
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 10 Tf 13 TL 40 800 Td\n{body}\nET{tail}".encode("latin-1"))
            page.replace_contents(stream)
        writer.write(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True, help="Katalog dane/ z repozytorium UZP")
    parser.add_argument("--out", type=Path, default=Path(".local/layout"))
    args = parser.parse_args()
    target = args.out / "dane"
    if target.exists():
        shutil.rmtree(target)
    documents = []
    # Seria „a”: układy 0–4 po kolei; seria „b”: ten sam przypadek w innym układzie (5, 6 albo przesunięty 0–4).
    jobs = [(case, "a", index % 5) for index, case in enumerate(CASES)]
    jobs += [(case, "b", (5, 6, (index + 2) % 5)[index % 3]) for index, case in enumerate(CASES)]
    for case, series, variant in jobs:
        source = args.data / f"przyklad_{case:02d}"
        gold = json.loads((source / "odwolanie.json").read_text(encoding="utf-8"))
        lines, footer = layout(variant, gold, source_facts(pdf_text(source / "odwolanie.pdf")))
        name = f"wariant_{case:02d}" + ("" if series == "a" else "b")
        folder = target / name
        folder.mkdir(parents=True)
        write_pdf(folder / "odwolanie.pdf", lines, footer)
        shutil.copy2(source / "odwolanie.json", folder / "odwolanie.json")
        documents.append({"split": "test", "type": "odwolanie", "prediction": f"{name}/odwolanie.json",
                          "reference": f"{name}/odwolanie.json", "variant": variant})
    (args.out / "manifest.json").write_text(json.dumps({"documents": documents}, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(f"{len(documents)} odwołań w {target}")


if __name__ == "__main__":
    main()
