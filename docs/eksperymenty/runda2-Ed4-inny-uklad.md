# Ed4, runda 2: odporność odwołań na inny układ

Baza: `b667a09` (scalona runda 1; walidacja UZP F1 0,9976). Model Qwen3.5-9B (HostYourAI), bez myślenia,
LLM_CONCURRENCY=1, odstęp 5 s.

## Zestaw „inny układ”

`evaluation/layout_variants.py` bierze 15 odwołań z development (przykłady 2, 3, 5, 6, 8, 9, 11, 15, 16,
19, 22, 25, 33, 41, 42: wszystkie powody poza 12, jeden i dwóch zamawiających, pisma z datą i bez) i składa
z wzorcowego JSON + fragmentów oryginału (pełnomocnicy, tryb, zarzuty) nowe PDF-y w innym układzie. Wzorce
JSON bez zmian. Dwie serie po 15 dokumentów (`wariant_NN`, `wariant_NNb`) = 30 odwołań. Układy:

0. „Pełnomocnik:” + „Adres do doręczeń: <kancelaria>, …, e-mail”, czynność „wobec czynności z dnia DD.MM.RRRR, polegającej na …”;
1. zamawiający przed odwołującym, „Działający przez:”, e-mail samego odwołującego w nagłówku, kancelaria
   i e-mail tylko przy podpisie, data i miejscowość na końcu, czynność „Dnia <data słownie> Zamawiający …”;
2. konsorcjum „a) X – pełnomocnik pozostałych wykonawców (lider konsorcjum), b) partner z KRS/NIP/REGON”,
   kancelaria w stopce każdej strony, czynność „Przedmiotem zaskarżenia jest …, dowiedział się w dniu RRRR-MM-DD”;
3. papier firmowy kancelarii na górze, pełnomocnik w zdaniu, „Niniejsze odwołanie dotyczy czynności … dokonanej …”;
4. strony w akapicie („Działając jako pełnomocnik wykonawcy …, ja, adw. X z kancelarii …”), „Sporządzono w
   Krakowie dnia …” (miejscowość w miejscowniku), „Zaskarżam następującą czynność: …”;
5. konsorcjum z partnerem wymienionym PIERWSZYM i liderem drugim, kancelaria w nagłówku;
6. nagłówek w dwóch kolumnach (odwołujący | zamawiający) sklejonych wierszami, jak po ekstrakcji tekstu.

Zamawiający zawsze dostaje własny e-mail (pułapka dla `pelnomocnik.mail`). Numery BZP ze spacją, TED jako
`RRRR/S 000-NNNNNN`. PDF: Helvetica z tablicą `/Differences` (polskie znaki), tylko pypdf.

Generowanie: `python evaluation/layout_variants.py --data <uzp>/dane --out .local/layout`, pomiar:
`experiment.py --split test --manifest .local/layout/manifest.json --data .local/layout/dane`
(split „test” w manifeście zestawu; przed pierwszym przebiegiem usunąć `.local/experiments/_input-test`).

## Przebiegi

| # | nazwa | zbiór | F1 | TP/FP/FN | uwagi |
|---|---|---|---|---|---|
| 1 | r2-Ed4-layout-base | inny układ, seria a (15) | 0,9619 | 303/24/0 | baza b667a09 |
| 2 | r2-Ed4-layout30-base | inny układ 30 | 0,9743 | 606/32/0 | baza b667a09 |
| 3 | r2-Ed4-layout30-prompt | inny układ 30 | **1,0000** | 606/0/0 | prompt ogólniejszy |
| 4 | r2-Ed4-prompt-dev | UZP development | **1,0000** | 1400/0/0 | odw./pełn./przelew 1,000; negatywy 9/9, 0 FP |
| 5 | r2-Ed4-prompt-val | UZP walidacja | **0,9976** | 424/2/0 | odw. 0,996, pełn./przelew 1,000; negatywy 7/7, 0 FP; ten sam 1 błąd powodu co w bazie |

### Co się sypało w bazie (przebiegi 1–2)

Jedyny błąd: **konsorcjum w układzie 2** (4 z 6 dokumentów) – model dodawał partnera konsorcjum jako drugi
element `Odwolujacy` (z pełnomocnikiem skopiowanym do obu), czyli 8 FP na dokument (wszystkie pola
odwołującego). Ciekawie: układ 5 (lider na drugim miejscu, partner pierwszy) przechodził 5/5 – lider był
wybierany dobrze, problemem było samo dopisywanie pozostałych członków. Prompt mówił tylko „przypisz nazwę
i identyfikatory wskazanego lidera”, bez tego, że lista ma wtedy jeden element.

Reszta trzymała się dobrze: daty pisma przy podpisie i w miejscowniku („Sporządzono w Krakowie”), czynność w
innym sformułowaniu i formacie daty, kancelaria w stopce/nagłówku/podpisie, „Adres do doręczeń”, dwie kolumny.
Reguły `fill_missing` z YAML (oparte na „adres do korespondencji”, „Zamawiający w dniu”) na innym układzie po
prostu się nie uruchamiają – nie dodały ani jednego FP (model nie zwracał tam null).

### Zmiana (prompt, sekcja Odwołanie)

- konsorcjum: lista `Odwolujacy` ma jeden element – lider (wskazany jako lider lub pełnomocnik pozostałych),
  niezależnie od kolejności, bez wskazania pierwszy wymieniony; pozostałych członków nie dodawać;
- `data`/`miejscowosc`: opis roli (miejsce i data sporządzenia pisma, zwykle nagłówek, rzadziej przy podpisie,
  miejscowość w mianowniku) zamiast „z nagłówka pierwszej strony”;
- pełnomocnik: przykłady etykiet „Pełnomocnik:”, „działający przez” obok „reprezentowana przez:”;
- kancelaria: „z adresu do korespondencji lub doręczeń, z papieru firmowego, stopki lub podpisu” zamiast
  dosłownej etykiety „adres do korespondencji: Kancelaria …”.

## Wynik

- Inny układ (30 odwołań): 0,9743 → **1,0000**. Per pole: wszystkie 8 pól `Odwolujacy[]` (krs, nazwa, nip,
  regon, przez-pelnomocnika, pelnomocnik.imie_nazwisko/nazwa/mail) 0,94 → 1,00 (po 4 FP mniej); pozostałe
  pola 1,00 już w bazie.
- UZP development 1,0000 (jak scalona runda 1), walidacja 0,9976 (identycznie jak `r1-merged-val`: ten sam
  błąd `czynnosc_powod_id`/`czynnosc_opis` w jednym odwołaniu – obszar Ed1–Ed3). Bez błędów API.

## Uwagi

- Zestaw jest łatwiejszy niż realne pisma (czysty tekst, krótkie zarzuty), więc 1,0 nie oznacza odporności
  na skany czy 30-stronicowe uzasadnienia; sprawdza tylko zależność od etykiet i kolejności sekcji.
- Reguły `fill_missing` są bezpieczne na innym układzie (nie odpalają), ale też nic tam nie dają. Ryzyko na
  realnych pismach: `czynnosc_dzien` z „Zamawiający w dniu …” nie ma `requires`, więc przy null od modelu
  wpisze datę jedynego takiego zdania, nawet jeśli dotyczy innej czynności (np. wezwania do wyjaśnień).
  Nie zmieniałem (brak przypadku w danych, a ruszałoby wynik UZP).
