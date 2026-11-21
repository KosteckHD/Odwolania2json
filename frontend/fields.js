// Opis rubryk dla znanych typów dokumentów (ścieżki zgodne ze schemas/*.schema.json).
// Typ spoza tej listy wyświetla się automatycznie z kluczy JSON (fallback),
// więc nowa klasa po stronie backendu działa w panelu bez zmian w kodzie.
//
// Rodzaje pól:
//   text    – zwykły tekst w rubryce
//   digits  – identyfikator w kratkach (NIP, KRS, REGON, PESEL)
//   date    – data RRRR-MM-DD w kratkach
//   code    – krótki kod liczbowy w kratkach (powód 1–12)
//   account – numer rachunku w kratkach, grupy po 4
//   amount  – kwota w złotych
//   bool    – 1/0 jako kratki „tak / nie”
//   enum    – wartość ze słownika (labels)
//   names   – lista obiektów { imie_nazwisko }
//
// Grupa z `list: true` to lista pozycji (np. kilku pełnomocników); `item` to nazwa pozycji
// w bierniku do przycisku „+ Dodaj …”.
//
// `hint` to krótka podpowiedź przy etykiecie. UZP chce imion i nazwisk w mianowniku
// („Mateusz Szymański”, nie „Mateusza Szymańskiego”), a w pismach bywają odmienione.

export const DOC_TYPES = {
  odwolanie: {
    label: "Odwołanie",
    groups: [
      {
        title: "Odwołanie",
        path: "OdwolanieKIO",
        fields: [
          { key: "data", label: "Data pisma", kind: "date" },
          { key: "miejscowosc", label: "Miejscowość", kind: "text" },
          { key: "czynnosc_dzien", label: "Dzień zaskarżonej czynności", kind: "date" },
          { key: "czynnosc_powod_id", label: "Powód odwołania (kod 1–12)", kind: "code" },
          { key: "czynnosc_opis", label: "Opis zaskarżonej czynności", kind: "text", wide: true },
        ],
      },
      {
        title: "Odwołujący",
        path: "Odwolujacy",
        list: true,
        item: "odwołującego",
        fields: [
          { key: "nazwa", label: "Nazwa", kind: "text", wide: true },
          { key: "krs", label: "Numer KRS", kind: "digits" },
          { key: "nip", label: "NIP", kind: "digits" },
          { key: "regon", label: "REGON", kind: "digits" },
          { key: "przez-pelnomocnika", label: "Działa przez pełnomocnika", kind: "bool" },
          { key: "pelnomocnik.imie_nazwisko", label: "Pełnomocnik: imię i nazwisko", kind: "text", hint: "w mianowniku" },
          { key: "pelnomocnik.nazwa", label: "Pełnomocnik: kancelaria", kind: "text" },
          { key: "pelnomocnik.mail", label: "Pełnomocnik: e-mail", kind: "text" },
        ],
      },
      {
        title: "Zamawiający",
        path: "Zamawiajacy",
        list: true,
        item: "zamawiającego",
        fields: [
          { key: "nazwa", label: "Nazwa", kind: "text", wide: true },
          { key: "krs", label: "Numer KRS", kind: "digits" },
          { key: "nip", label: "NIP", kind: "digits" },
          { key: "regon", label: "REGON", kind: "digits" },
          { key: "prowadzacy_postepowanie", label: "Prowadzi postępowanie", kind: "bool" },
        ],
      },
      {
        title: "Zamówienie publiczne",
        path: "ZamowieniePubliczne",
        fields: [
          { key: "numer_ted", label: "Numer ogłoszenia TED", kind: "text" },
          { key: "numer_bzp", label: "Numer ogłoszenia BZP", kind: "text" },
          { key: "numer_postepowania", label: "Numer postępowania", kind: "text" },
          { key: "tytul", label: "Tytuł zamówienia", kind: "text", wide: true },
        ],
      },
    ],
  },

  pelnomocnictwo: {
    label: "Pełnomocnictwo",
    groups: [
      {
        title: "Mocodawca",
        path: "mocodawca",
        list: true,
        item: "mocodawcę",
        fields: [
          { key: "data.nazwa", label: "Nazwa", kind: "text", wide: true },
          { key: "data.typ", label: "Rodzaj podmiotu", kind: "enum", labels: { osoba_prawna: "Osoba prawna", osoba_fizyczna: "Osoba fizyczna" } },
          { key: "data.imie_nazwisko", label: "Imię i nazwisko osoby fizycznej", kind: "text", hint: "w mianowniku" },
          { key: "data.krs", label: "Numer KRS", kind: "digits" },
          { key: "data.nip", label: "NIP", kind: "digits" },
          { key: "podpisujacy", label: "Osoby podpisujące", kind: "names", wide: true, hint: "w mianowniku" },
        ],
      },
      {
        title: "Pełnomocnik",
        path: "pelnomocnicy",
        list: true,
        item: "pełnomocnika",
        fields: [
          { key: "imie_nazwisko", label: "Imię i nazwisko", kind: "text", hint: "w mianowniku" },
          { key: "pesel", label: "PESEL", kind: "digits", integer: true },
        ],
      },
    ],
  },

  przelew: {
    label: "Potwierdzenie przelewu",
    groups: [
      {
        title: "Przelew bankowy",
        path: "przelew_bankowy",
        fields: [
          { key: "data_operacji", label: "Data operacji", kind: "date" },
          { key: "kwota", label: "Kwota", kind: "amount" },
          { key: "z_rachunku", label: "Z rachunku (nadawca)", kind: "account", wide: true },
          { key: "na_rachunek", label: "Na rachunek (odbiorca)", kind: "account", wide: true },
          { key: "numer_transakcji", label: "Numer transakcji", kind: "text" },
          { key: "tytul", label: "Tytuł przelewu", kind: "text", wide: true },
        ],
      },
    ],
  },
};

export function typeLabel(type) {
  return DOC_TYPES[type]?.label ?? type;
}

/** Odczyt wartości po ścieżce z kropkami, np. "pelnomocnik.nazwa". */
export function getPath(object, path) {
  return path.split(".").reduce((value, key) => (value == null ? undefined : value[key]), object);
}

/**
 * Pusta pozycja listy: ta sama struktura co wzór (np. pierwsza pozycja od modelu),
 * a gdy wzoru brak, struktura z kluczy rubryk. Liście dostają null, tablice [].
 */
export function emptyListItem(fields, template = null) {
  const blank = (v) => (Array.isArray(v) ? [] : v && typeof v === "object"
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, blank(x)])) : null);
  const item = template && typeof template === "object" && !Array.isArray(template) ? blank(template) : {};
  for (const f of fields) {
    const keys = f.key.split(".");
    let target = item;
    keys.slice(0, -1).forEach((k) => { if (!target[k] || typeof target[k] !== "object") target[k] = {}; target = target[k]; });
    if (!(keys.at(-1) in target)) target[keys.at(-1)] = f.kind === "names" ? [] : null;
  }
  return item;
}
