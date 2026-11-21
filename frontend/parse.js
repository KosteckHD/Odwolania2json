// Zamiana tekstu (wpisanego albo zaznaczonego w PDF-ie) na wartość rubryki
// zgodną ze schematem UZP. Funkcje są czyste, więc łatwo je testować.

const MONTHS = {
  stycznia: 1, styczeń: 1, lutego: 2, luty: 2, marca: 3, marzec: 3, kwietnia: 4, kwiecień: 4,
  maja: 5, maj: 5, czerwca: 6, czerwiec: 6, lipca: 7, lipiec: 7, sierpnia: 8, sierpień: 8,
  września: 9, wrzesień: 9, października: 10, październik: 10, listopada: 11, listopad: 11,
  grudnia: 12, grudzień: 12,
};

/** Oczekiwana liczba cyfr identyfikatora po nazwie klucza. */
export function expectedDigits(key) {
  const k = key.split(".").at(-1).toLowerCase();
  if (k === "krs") return [10];
  if (k === "nip") return [10];
  if (k === "regon") return [9, 14];
  if (k === "pesel") return [11];
  if (k.includes("rachun")) return [26];
  return [];
}

/** Z tekstu typu „KRS: 0000 054 588” wybiera sam numer: 0000054588. */
export function pickDigits(text, lengths = []) {
  const runs = (String(text).match(/\d[\d\s.\-\/]*\d|\d/g) ?? []).map((r) => r.replace(/\D/g, ""));
  if (!runs.length) return "";
  const exact = runs.find((r) => lengths.includes(r.length));
  if (exact) return exact;
  // numer rozbity na kilka grup bez separatorów, np. „PL 61 1010 1010 …”
  const all = runs.join("");
  if (lengths.includes(all.length)) return all;
  return runs.reduce((a, b) => (b.length > a.length ? b : a));
}

/** Data z „13.10.2025”, „2025-10-13” albo „13 października 2025 r.” → „2025-10-13”. */
export function pickDate(text) {
  const t = String(text).toLowerCase();
  let m = t.match(/(\d{4})[-.\/](\d{1,2})[-.\/](\d{1,2})/);
  if (m) return iso(m[1], m[2], m[3]);
  m = t.match(/(\d{1,2})[-.\/](\d{1,2})[-.\/](\d{4})/);
  if (m) return iso(m[3], m[2], m[1]);
  m = t.match(/(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})/);
  if (m && MONTHS[m[2]]) return iso(m[3], MONTHS[m[2]], m[1]);
  return null;
}

function iso(y, mo, d) {
  const year = Number(y), month = Number(mo), day = Number(d);
  if (month < 1 || month > 12 || day < 1) return null;
  // dzień musi istnieć w danym miesiącu (31.04 albo 29.02 w roku zwykłym → null)
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (day > daysInMonth) return null;
  return `${y}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** Kwota z „10 000,00 zł” albo „10.000,00 PLN” → 10000. */
export function pickAmount(text) {
  const m = String(text).match(/\d[\d\s. ]*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?/);
  if (!m) return null;
  let s = m[0].replace(/[\s ]/g, "");
  if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
  else if (/\.\d{3}(\.|$)/.test(s)) s = s.replace(/\./g, "");
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Kod powodu odwołania 1–12. */
export function pickCode(text) {
  const n = Number((String(text).match(/\d{1,2}/) ?? [])[0]);
  return Number.isInteger(n) && n >= 1 && n <= 12 ? n : null;
}

/** Tekst bez etykiety na początku, np. „Odwołujący: STRABAG Sp. z o.o.” → „STRABAG Sp. z o.o.”. */
export function pickText(text) {
  let t = String(text).replace(/\s+/g, " ").trim();
  const colon = t.indexOf(":");
  if (colon > 0 && colon < 40 && t.slice(colon + 1).trim()) t = t.slice(colon + 1).trim();
  return t.replace(/^[„"'«]+|[”"'»]+$/g, "").trim();
}

/* ---------- sumy kontrolne identyfikatorów ----------
   Zwracają true (zgadza się), false (nie zgadza się) albo null (nie da się sprawdzić:
   inna długość, znaki spoza cyfr, identyfikator bez sumy kontrolnej, np. KRS). */

const weighted = (digits, weights) => weights.reduce((sum, w, i) => sum + w * Number(digits[i]), 0);

/** NIP: wagi 6,5,7,2,3,4,5,6,7, reszta z dzielenia przez 11 to ostatnia cyfra (10 = numer błędny). */
export function nipValid(value) {
  const d = String(value ?? "");
  if (!/^\d{10}$/.test(d)) return null;
  const r = weighted(d, [6, 5, 7, 2, 3, 4, 5, 6, 7]) % 11;
  return r !== 10 && r === Number(d[9]);
}

/** REGON 9- i 14-cyfrowy: reszta z 11 (10 liczy się jako 0) to ostatnia cyfra. */
export function regonValid(value) {
  const d = String(value ?? "");
  const weights = d.length === 9 ? [8, 9, 2, 3, 4, 5, 6, 7]
    : d.length === 14 ? [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8] : null;
  if (!weights || !/^\d+$/.test(d)) return null;
  const r = weighted(d, weights) % 11;
  return (r === 10 ? 0 : r) === Number(d.at(-1));
}

/** PESEL: wagi 1,3,7,9,1,3,7,9,1,3; cyfra kontrolna = (10 − suma mod 10) mod 10. */
export function peselValid(value) {
  const d = String(value ?? "");
  if (!/^\d{11}$/.test(d)) return null;
  return (10 - (weighted(d, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]) % 10)) % 10 === Number(d[10]);
}

/** Numer rachunku NRB (26 cyfr) jako IBAN PL: reszta z dzielenia przez 97 równa 1. */
export function accountValid(value) {
  const d = String(value ?? "").replace(/\s/g, "");
  if (!/^\d{26}$/.test(d)) return null;
  // „PL” → 25 21; liczba za długa na Number, więc reszta liczona kawałkami
  const moved = `${d.slice(2)}2521${d.slice(0, 2)}`;
  let rest = 0;
  for (const ch of moved) rest = (rest * 10 + Number(ch)) % 97;
  return rest === 1;
}

/** Sprawdzenie sumy kontrolnej po nazwie klucza rubryki (nip, regon, pesel, rachunek). KRS nie ma sumy. */
export function checksumValid(key, value) {
  if (value === null || value === undefined || value === "") return null;
  const k = key.split(".").at(-1).toLowerCase();
  if (k === "nip") return nipValid(value);
  if (k === "regon") return regonValid(value);
  if (k === "pesel") return peselValid(String(value).padStart(11, "0"));
  if (k.includes("rachun")) return accountValid(value);
  return null;
}

export const CHECKSUM_WARNING = "suma kontrolna się nie zgadza, sprawdź cyfry";
