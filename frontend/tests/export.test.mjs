// Testy eksportu i ręcznej zmiany typu (export.js) oraz ich śladu w kopii roboczej (draft.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { DOC_TYPES } from "../fields.js";
import { buildResultFiles, emptyDataFor, jsonName, retypeEntry, safeName } from "../export.js";
import { alignDraft, buildDraft, unsavedPositions } from "../draft.js";

const files = [{ name: "odwolanie.pdf", size: 10 }, { name: "ogloszenie.pdf", size: 20 }, { name: "skan.pdf", size: 30 }];
const odwData = { OdwolanieKIO: { miejscowosc: "Pruszków" }, Odwolujacy: [{ nazwa: "A" }] };
const base = () => [
  { filename: "odwolanie.pdf", status: "ok", type: "odwolanie", data: structuredClone(odwData) },
  { filename: "ogloszenie.pdf", status: "unknown", type: null, data: null },
  { filename: "skan.pdf", status: "error", type: null, data: null, error: { code: "ocr_required" } },
];
const exportOf = (results, edits = []) =>
  buildResultFiles({ files, results, dataAt: (i) => edits[i] ?? results[i].data, caseName: "KIO 1/26" });

test("nazwy plików wynikowych", () => {
  assert.equal(jsonName("Pismo.PDF"), "Pismo.json");
  assert.equal(safeName('KIO 1/26: "x"'), "KIO 1_26_ _x_");
});

test("eksport bez zmian: JSON dla ok, {} dla nierozpoznanego, brak pliku dla błędu", () => {
  const out = exportOf(base());
  assert.deepEqual(out.map((f) => f.name), ["KIO 1_26/odwolanie.json", "KIO 1_26/ogloszenie.json"]);
  assert.deepEqual(JSON.parse(out[0].text), odwData);
  assert.equal(out[1].text, "{}");
});

test("emptyDataFor: pusty JSON w formacie typu (obiekty z null, listy puste)", () => {
  assert.deepEqual(emptyDataFor(DOC_TYPES.przelew), {
    przelew_bankowy: { data_operacji: null, kwota: null, z_rachunku: null, na_rachunek: null, numer_transakcji: null, tytul: null },
  });
  const pel = emptyDataFor(DOC_TYPES.pelnomocnictwo);
  assert.deepEqual(pel, { mocodawca: [], pelnomocnicy: [] });
});

test("nierozpoznany → typ ustawiony ręcznie: w eksporcie JSON wybranego typu zamiast {}", () => {
  const results = base();
  results[1] = retypeEntry(results[1], "przelew");
  assert.equal(results[1].status, "ok");
  assert.equal(results[1].manualType, true);
  assert.equal(results[1].previous.status, "unknown");
  const edits = [];
  edits[1] = structuredClone(results[1].data);
  edits[1].przelew_bankowy.kwota = 7500;
  const text = exportOf(results, edits)[1].text;
  assert.notEqual(text, "{}");
  assert.deepEqual(JSON.parse(text).przelew_bankowy.kwota, 7500);
  assert.ok("na_rachunek" in JSON.parse(text).przelew_bankowy);
  // bez żadnego wpisu też format typu, nie {}
  assert.deepEqual(JSON.parse(exportOf(results)[1].text), emptyDataFor(DOC_TYPES.przelew));
});

test("rozpoznany → inny typ: eksport w formacie nowego typu, powrót przywraca dane modelu", () => {
  const results = base();
  const changed = retypeEntry(results[0], "pelnomocnictwo");
  assert.deepEqual(changed.data, { mocodawca: [], pelnomocnicy: [] });
  results[0] = changed;
  assert.deepEqual(JSON.parse(exportOf(results)[0].text), { mocodawca: [], pelnomocnicy: [] });
  // druga zmiana pamięta pierwotny wpis od modelu, nie pośredni
  const again = retypeEntry(changed, "przelew");
  assert.equal(again.previous.type, "odwolanie");
  results[0] = again.previous;
  assert.deepEqual(JSON.parse(exportOf(results)[0].text), odwData);
});

test("kopia robocza: ręcznie ustawiony typ liczy się jako poprawka i wraca po przywróceniu", () => {
  const results = base();
  results[1] = retypeEntry(results[1], "przelew");
  const draft = buildDraft({ files, results, edits: [], now: 1 });
  assert.ok(draft);
  assert.equal(draft.changes, 1);
  assert.equal(draft.docsEdited, 1);
  const aligned = alignDraft(draft, files);
  assert.equal(aligned.results[1].type, "przelew");
  assert.equal(aligned.results[1].manualType, true);
  // bez zmian typu i bez poprawek nie ma czego chronić
  assert.equal(buildDraft({ files, results: base(), edits: [], now: 1 }), null);
});

test("niepobrane: sama zmiana typu wymaga pobrania, po pobraniu znika", () => {
  const results = base();
  results[1] = retypeEntry(results[1], "przelew");
  assert.deepEqual(unsavedPositions({ results, edits: [], saved: [] }), [1]);
  const saved = [];
  saved[1] = JSON.stringify(results[1].data);
  assert.deepEqual(unsavedPositions({ results, edits: [], saved }), []);
});

test("emptyDataFor dla typu ze schematu (kreator): pola z poziomu głównego bez grupy", async () => {
  const { schemaToSpec } = await import("../fields.js");
  const spec = schemaToSpec({ type: "object", properties: {
    numer: { type: ["string", "null"] }, data_odbioru: { type: ["string", "null"], format: "date" },
    podpisane: { type: ["boolean", "null"] }, osoby: { type: "array", items: { type: "object", properties: { imie: { type: "string" } } } },
  } }, "Potwierdzenie odbioru");
  assert.deepEqual(emptyDataFor(spec), { numer: null, data_odbioru: null, podpisane: null, osoby: [] });
  const retyped = retypeEntry({ filename: "x.pdf", status: "unknown", type: null, data: null }, "potwierdzenie_odbioru", spec);
  assert.deepEqual(retyped.data, { numer: null, data_odbioru: null, podpisane: null, osoby: [] });
});
