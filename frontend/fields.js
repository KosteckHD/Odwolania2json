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
    if (!(keys.at(-1) in target)) target[keys.at(-1)] = f.kind === "names" || f.kind === "lines" ? [] : null;
  }
  return item;
}

/* ---------- formularz ze schematu JSON (typy dodane kreatorem, spoza DOC_TYPES) ---------- */

/** „data_odbioru” → „Data odbioru”. */
export function prettyKey(key) {
  const t = String(key).replace(/[_\-.]+/g, " ").replace(/([a-ząćęłńóśźż])([A-Z])/g, "$1 $2").trim().toLowerCase();
  return t ? t[0].toUpperCase() + t.slice(1) : String(key);
}

const typesOf = (schema) => (Array.isArray(schema?.type) ? schema.type : [schema?.type]).filter((t) => t && t !== "null");

/** Długości z wzorca cyfr, np. ^[0-9]{9}$ → [9], ^\d{9}(\d{5})?$ → brak (zwykłe kratki). */
function digitLengths(pattern) {
  const m = String(pattern).match(/^\^(?:\[0-9\]|\d)\{(\d+)(?:,(\d+))?\}\$$/);
  if (!m) return null;
  return m[2] ? [Number(m[1]), Number(m[2])] : [Number(m[1])];
}

/** Rubryka dla prostej wartości schematu; null, gdy to obiekt albo tablica obiektów. */
export function fieldFromSchema(key, schema, label = schema?.description || prettyKey(key.split(".").at(-1))) {
  const types = typesOf(schema);
  const type = types[0];
  if (type === "boolean") return { key, label, kind: "bool" };
  if (type === "number" || type === "integer") {
    const money = /kwot|amount|cena|oplat|opłat|wartosc|wartość/i.test(key);
    return { key, label, kind: money ? "amount" : "number", integer: type === "integer" };
  }
  if (type === "string") {
    if (schema.format === "date") return { key, label, kind: "date" };
    if (typeof schema.pattern === "string" && /^\^(?:\[0-9\]|\d)(?:\+|\*|\{\d+(?:,\d+)?\})\$$/.test(schema.pattern)) {
      const lengths = digitLengths(schema.pattern);
      return { key, label, kind: "digits", ...(lengths ? { lengths } : {}) };
    }
    if (schema.enum?.length) return { key, label, kind: "enum", labels: Object.fromEntries(schema.enum.filter((v) => v !== null).map((v) => [v, prettyKey(v)])) };
    const long = (schema.maxLength ?? 0) > 120 || /opis|tytul|tytuł|uwagi|tresc|treść|nazwa|adres/i.test(key);
    return { key, label, kind: "text", ...(long ? { wide: true } : {}) };
  }
  if (type === "array") {
    const item = schema.items ?? {};
    if (typesOf(item)[0] === "object") return null;
    const itemType = typesOf(item)[0];
    return { key, label, kind: "lines", wide: true, numeric: itemType === "number" || itemType === "integer" };
  }
  if (type === "object") return null;
  return { key, label, kind: "text" };
}

/** Rubryki obiektu: proste pola, a zagnieżdżone obiekty spłaszczone do kluczy z kropką. */
function objectFields(schema, prefix = "") {
  const fields = [];
  for (const [key, prop] of Object.entries(schema?.properties ?? {})) {
    const path = prefix ? `${prefix}.${key}` : key;
    const field = fieldFromSchema(path, prop);
    if (field) fields.push(field);
    else if (typesOf(prop)[0] === "object") fields.push(...objectFields(prop, path));
  }
  return fields;
}

/**
 * Opis formularza (jak w DOC_TYPES) zbudowany ze schematu klasy:
 * proste pola z poziomu głównego w jednej grupie, zagnieżdżony obiekt jako osobna grupa,
 * tablica obiektów jako grupa listy (z dodawaniem i usuwaniem pozycji).
 * @returns {{label: string, fromSchema: true, groups: Array}}
 */
export function schemaToSpec(schema, label) {
  const root = [];
  const groups = [];
  for (const [key, prop] of Object.entries(schema?.properties ?? {})) {
    const type = typesOf(prop)[0];
    const title = prop?.description || prettyKey(key);
    if (type === "object") {
      groups.push({ title, path: key, fields: objectFields(prop) });
    } else if (type === "array" && typesOf(prop.items)[0] === "object") {
      groups.push({ title, path: key, list: true, item: "pozycję", fields: objectFields(prop.items) });
    } else {
      const field = fieldFromSchema(key, prop);
      if (field) root.push(field);
    }
  }
  if (root.length) groups.unshift({ title: "Dane dokumentu", path: "", root: true, fields: root });
  return { label, fromSchema: true, groups };
}
