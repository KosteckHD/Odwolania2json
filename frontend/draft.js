// Kopia robocza ręcznych poprawek w pamięci przeglądarki.
// Same czyste funkcje (bez DOM i bez localStorage), żeby dało się je testować w Node.
// Kopia trzyma wyniki z backendu i poprawione dane, nigdy samych PDF-ów.
// Sprawę rozpoznajemy po nazwach i rozmiarach plików, niezależnie od kolejności.

export const DRAFT_STORAGE_KEY = "o2j-drafts";
export const DRAFT_VERSION = 1;
export const DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000;   // kopie starsze niż tydzień są pomijane
export const DRAFT_MAX_CASES = 5;                      // najwyżej tyle spraw naraz, najnowsze

const emptyStore = () => ({ v: DRAFT_VERSION, cases: {} });

export const fileKey = (file) => `${file.name}|${file.size}`;

/** Klucz sprawy: posortowane „nazwa|rozmiar” wszystkich plików. */
export function caseKey(files) {
  return files.map(fileKey).sort().join("\n");
}

/** Liczba wartości (liści), którymi `edited` różni się od `original`. */
export function countChanges(edited, original) {
  if (!edited) return 0;
  let n = 0;
  const walk = (a, b) => {
    if (a && typeof a === "object") {
      const other = b && typeof b === "object" ? b : {};
      new Set([...Object.keys(a), ...Object.keys(other)]).forEach((k) => walk(a[k], other[k]));
    } else if (JSON.stringify(a ?? null) !== JSON.stringify(b ?? null)) n += 1;
  };
  walk(edited, original);
  return n;
}

/**
 * Buduje kopię roboczą sprawy. Zwraca null, gdy nie ma żadnej ręcznej poprawki
 * (wtedy nie ma czego chronić).
 */
export function buildDraft({ files, results, edits, meta = null, caseName = null, now = Date.now() }) {
  if (!results || !files.length) return null;
  let changes = 0, docsEdited = 0;
  const docs = files.map((file, i) => {
    const result = results[i] ?? null;
    const n = countChanges(edits[i], result?.data);
    changes += n;
    if (n) docsEdited += 1;
    return { file: fileKey(file), result, edited: n ? edits[i] : null };
  });
  if (!changes) return null;
  return { v: DRAFT_VERSION, key: caseKey(files), caseName, savedAt: now, meta, changes, docsEdited, docs };
}

/** Odczyt magazynu z tekstu z localStorage. Uszkodzone, obce i przeterminowane wpisy są pomijane. */
export function parseStore(raw, now = Date.now()) {
  let store = null;
  try { store = JSON.parse(raw ?? "null"); } catch { store = null; }
  if (!store || store.v !== DRAFT_VERSION || !store.cases || typeof store.cases !== "object") return emptyStore();
  const cases = {};
  for (const [key, draft] of Object.entries(store.cases)) {
    const fresh = Number.isFinite(draft?.savedAt) && now - draft.savedAt < DRAFT_TTL_MS;
    if (fresh && draft.v === DRAFT_VERSION && draft.key === key && Array.isArray(draft.docs)) cases[key] = draft;
  }
  return { v: DRAFT_VERSION, cases };
}

/** Wstawia (draft) albo usuwa (null) kopię sprawy; zostawia `max` najnowszych spraw. */
export function putDraft(store, key, draft, max = DRAFT_MAX_CASES) {
  const cases = { ...store.cases };
  if (draft) cases[key] = draft;
  else delete cases[key];
  const keep = Object.entries(cases).sort((a, b) => b[1].savedAt - a[1].savedAt).slice(0, max);
  return { v: DRAFT_VERSION, cases: Object.fromEntries(keep) };
}

/** Kopia dla dokładnie tego zestawu plików albo null. */
export function findDraft(store, files) {
  if (!files.length) return null;
  return store.cases[caseKey(files)] ?? null;
}

/**
 * Układa wyniki i poprawki z kopii w kolejności bieżących plików
 * (pliki mogły zostać wybrane w innej kolejności). Null, gdy zestaw się nie zgadza.
 */
export function alignDraft(draft, files) {
  const pool = new Map();
  for (const doc of draft.docs) {
    const queue = pool.get(doc.file) ?? [];
    queue.push(doc);
    pool.set(doc.file, queue);
  }
  const results = [], edits = [];
  for (const [i, file] of files.entries()) {
    const doc = pool.get(fileKey(file))?.shift();
    if (!doc?.result) return null;
    results[i] = doc.result;
    if (doc.edited) edits[i] = doc.edited;
  }
  if ([...pool.values()].some((queue) => queue.length)) return null;
  return { results, edits };
}

/**
 * Pozycje dokumentów z ręcznymi poprawkami, które nie trafiły jeszcze do pobranego
 * JSON-a ani ZIP-a. `saved[i]` to JSON danych z chwili ostatniego pobrania.
 */
export function unsavedPositions({ results, edits, saved = [] }) {
  if (!results) return [];
  const out = [];
  edits.forEach((data, i) => {
    if (!data || !countChanges(data, results[i]?.data)) return;
    if (saved[i] !== JSON.stringify(data)) out.push(i);
  });
  return out;
}

export function plural(n, one, few, many) {
  if (n === 1) return one;
  const d = n % 10, t = n % 100;
  return d >= 2 && d <= 4 && (t < 12 || t > 14) ? few : many;
}

const two = (n) => String(n).padStart(2, "0");

/** „dziś o 14:05”, „wczoraj o 9:30”, „18.11.2026 o 16:00” (czas lokalny). */
export function formatWhen(savedAt, now = Date.now()) {
  const d = new Date(savedAt);
  const time = `${d.getHours()}:${two(d.getMinutes())}`;
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(new Date(now)) - day(d)) / 86400000);
  if (diff === 0) return `dziś o ${time}`;
  if (diff === 1) return `wczoraj o ${time}`;
  return `${d.getDate()}.${two(d.getMonth() + 1)}.${d.getFullYear()} o ${time}`;
}

/** Opis kopii do pytania „Przywrócić poprawki?”. */
export function describeDraft(draft, now = Date.now()) {
  const { changes, docsEdited } = draft;
  return `${changes} ${plural(changes, "poprawka", "poprawki", "poprawek")} w ${docsEdited} ${plural(docsEdited, "dokumencie", "dokumentach", "dokumentach")} (zapis: ${formatWhen(draft.savedAt, now)})`;
}
