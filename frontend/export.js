// Eksport wyników i ręczna zmiana typu dokumentu (czyste funkcje, testy: tests/export.test.mjs).
import { DOC_TYPES, emptyListItem } from "./fields.js";

export const jsonName = (fileName) => `${fileName.replace(/\.pdf$/i, "")}.json`;
export const safeName = (name) => name.replace(/[\\/:*?"<>|]+/g, "_").trim() || "sprawa";

/**
 * Pusty JSON w formacie typu: obiekty z wartościami null, listy puste.
 * @param {{groups: Array<{path:string, list?:boolean, fields:Array}>}} spec opis rubryk (DOC_TYPES[typ])
 */
export function emptyDataFor(spec) {
  const data = {};
  for (const group of spec?.groups ?? []) {
    data[group.path] = group.list ? [] : emptyListItem(group.fields);
  }
  return data;
}

/**
 * Wpis wyniku po ręcznym ustawieniu typu: status ok, pusty formularz wybranego typu.
 * Pierwotny wpis (od modelu) zostaje w `previous`, żeby dało się go przywrócić.
 */
export function retypeEntry(entry, type, spec = DOC_TYPES[type]) {
  const previous = entry?.manualType ? entry.previous : entry;
  return {
    filename: entry?.filename ?? previous?.filename,
    status: "ok",
    type,
    data: emptyDataFor(spec),
    manualType: true,
    previous: previous ?? null,
  };
}

/**
 * Pliki wynikowe jak w output/<sprawa>/: JSON danych dla rozpoznanych (także z typem ustawionym
 * ręcznie), `{}` dla nierozpoznanych (wymóg UZP), brak pliku przy błędzie (jak w CLI).
 * @param {{files: {name:string}[], results: object[], dataAt: (i:number) => object, caseName?: string|null}} input
 */
export function buildResultFiles({ files, results, dataAt, caseName = null }) {
  if (!results) return [];
  const folder = safeName(caseName ?? "sprawa");
  const used = new Set();
  const out = [];
  results.forEach((r, i) => {
    if (r?.status !== "ok" && r?.status !== "unknown") return;
    let name = jsonName(files[i].name);
    for (let k = 2; used.has(name); k++) name = jsonName(files[i].name).replace(/\.json$/, ` (${k}).json`);
    used.add(name);
    out.push({ name: `${folder}/${name}`, text: r.status === "ok" ? `${JSON.stringify(dataAt(i), null, 2)}\n` : "{}" });
  });
  return out;
}
