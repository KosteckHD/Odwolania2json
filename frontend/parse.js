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
