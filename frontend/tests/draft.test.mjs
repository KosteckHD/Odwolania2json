// Testy kopii roboczej poprawek (draft.js): klucz sprawy, budowa kopii, magazyn, dopasowanie plików.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DRAFT_MAX_CASES, DRAFT_TTL_MS, DRAFT_VERSION, alignDraft, buildDraft, caseKey, countChanges,
  describeDraft, fileKey, findDraft, formatWhen, parseStore, putDraft, unsavedPositions,
} from "../draft.js";

const file = (name, size) => ({ name, size });
const files = [file("odwolanie.pdf", 1647), file("pelnomocnictwo.pdf", 899), file("ogloszenie.pdf", 760)];
const results = [
  { status: "ok", type: "odwolanie", data: { OdwolanieKIO: { miejscowosc: "Pruszków", data: "2025-10-13" }, Odwolujacy: [{ nazwa: "A" }] } },
  { status: "ok", type: "pelnomocnictwo", data: { Mocodawca: { nazwa: "B" } } },
  { status: "unknown", type: null, data: null },
];
const NOW = new Date(2026, 10, 21, 17, 5).getTime();

const editedOdw = () => {
  const d = structuredClone(results[0].data);
  d.OdwolanieKIO.miejscowosc = "Warszawa";
  d.Odwolujacy[0].nip = "1234567890";
  return d;
};

test("fileKey i caseKey: nazwa z rozmiarem, kolejność plików bez znaczenia", () => {
  assert.equal(fileKey(file("a.pdf", 10)), "a.pdf|10");
  assert.equal(caseKey(files), caseKey([...files].reverse()));
  assert.notEqual(caseKey(files), caseKey([file("odwolanie.pdf", 1648), files[1], files[2]]));
  assert.notEqual(caseKey(files), caseKey(files.slice(0, 2)));
});

test("countChanges: liczy zmienione, dodane i usunięte wartości", () => {
  assert.equal(countChanges(null, results[0].data), 0);
  assert.equal(countChanges(structuredClone(results[0].data), results[0].data), 0);
  assert.equal(countChanges(editedOdw(), results[0].data), 2);
  const removed = structuredClone(results[0].data);
  removed.OdwolanieKIO.data = null;
  assert.equal(countChanges(removed, results[0].data), 1);
  assert.equal(countChanges({ a: [{ x: 1 }, { x: 2 }] }, { a: [{ x: 1 }] }), 1);
});

test("buildDraft: bez poprawek nie ma kopii", () => {
  assert.equal(buildDraft({ files, results, edits: [], now: NOW }), null);
  assert.equal(buildDraft({ files, results, edits: [structuredClone(results[0].data)], now: NOW }), null);
  assert.equal(buildDraft({ files, results: null, edits: [editedOdw()], now: NOW }), null);
});

test("buildDraft: wyniki, poprawki i liczniki", () => {
  const draft = buildDraft({ files, results, edits: [editedOdw()], meta: { model: "m", seconds: 1.4 }, caseName: "KIO 1/25", now: NOW });
  assert.equal(draft.v, DRAFT_VERSION);
  assert.equal(draft.key, caseKey(files));
  assert.equal(draft.savedAt, NOW);
  assert.equal(draft.caseName, "KIO 1/25");
  assert.deepEqual(draft.meta, { model: "m", seconds: 1.4 });
  assert.equal(draft.changes, 2);
  assert.equal(draft.docsEdited, 1);
  assert.deepEqual(draft.docs.map((d) => d.file), files.map(fileKey));
  assert.equal(draft.docs[0].edited.OdwolanieKIO.miejscowosc, "Warszawa");
  assert.equal(draft.docs[1].edited, null);
  assert.equal(draft.docs[2].result.status, "unknown");
  // kopia nie zawiera samych plików
  assert.ok(!JSON.stringify(draft).includes("arrayBuffer"));
});

test("parseStore: uszkodzony, obcy albo przeterminowany wpis jest pomijany", () => {
  assert.deepEqual(parseStore(null, NOW), { v: DRAFT_VERSION, cases: {} });
  assert.deepEqual(parseStore("{nie json", NOW), { v: DRAFT_VERSION, cases: {} });
  assert.deepEqual(parseStore(JSON.stringify({ v: 99, cases: {} }), NOW).cases, {});
  const fresh = buildDraft({ files, results, edits: [editedOdw()], now: NOW - 1000 });
  const old = { ...buildDraft({ files: files.slice(0, 2), results, edits: [editedOdw()], now: NOW - DRAFT_TTL_MS - 1 }) };
  const wrongKey = { ...fresh, key: "inny" };
  const raw = JSON.stringify({ v: DRAFT_VERSION, cases: { [fresh.key]: fresh, [old.key]: old, zly: wrongKey } });
  assert.deepEqual(Object.keys(parseStore(raw, NOW).cases), [fresh.key]);
});

test("putDraft: zapis, usunięcie i limit najnowszych spraw", () => {
  let store = parseStore(null, NOW);
  for (let i = 0; i < DRAFT_MAX_CASES + 2; i++) {
    const fs = [file(`sprawa${i}.pdf`, 100 + i)];
    const draft = buildDraft({ files: fs, results: [results[1]], edits: [{ Mocodawca: { nazwa: `X${i}` } }], now: NOW + i });
    store = putDraft(store, draft.key, draft);
  }
  const keys = Object.keys(store.cases);
  assert.equal(keys.length, DRAFT_MAX_CASES);
  assert.ok(!keys.includes(caseKey([file("sprawa0.pdf", 100)])), "najstarsza sprawa wypada");
  assert.ok(keys.includes(caseKey([file(`sprawa${DRAFT_MAX_CASES + 1}.pdf`, 100 + DRAFT_MAX_CASES + 1)])));
  const removed = putDraft(store, keys[0], null);
  assert.equal(Object.keys(removed.cases).length, DRAFT_MAX_CASES - 1);
  assert.equal(Object.keys(store.cases).length, DRAFT_MAX_CASES, "putDraft nie zmienia przekazanego magazynu");
});

test("findDraft i alignDraft: ta sama sprawa w innej kolejności", () => {
  const draft = buildDraft({ files, results, edits: [editedOdw()], now: NOW });
  const store = putDraft(parseStore(null, NOW), draft.key, draft);
  const reordered = [files[2], files[0], files[1]];
  assert.equal(findDraft(store, reordered), draft);
  assert.equal(findDraft(store, files.slice(0, 2)), null);
  assert.equal(findDraft(store, []), null);
  const aligned = alignDraft(draft, reordered);
  assert.deepEqual(aligned.results.map((r) => r.status), ["unknown", "ok", "ok"]);
  assert.equal(aligned.edits[1].OdwolanieKIO.miejscowosc, "Warszawa");
  assert.equal(aligned.edits[0], undefined);
  assert.equal(aligned.edits[2], undefined);
});

test("alignDraft: duplikaty nazw i rozmiarów oraz niezgodny zestaw", () => {
  const twin = [file("skan.pdf", 500), file("skan.pdf", 500)];
  const rs = [{ status: "ok", type: "x", data: { a: 1 } }, { status: "ok", type: "x", data: { a: 2 } }];
  const draft = buildDraft({ files: twin, results: rs, edits: [undefined, { a: 3 }], now: NOW });
  const aligned = alignDraft(draft, twin);
  assert.deepEqual(aligned.results.map((r) => r.data.a), [1, 2]);
  assert.deepEqual(aligned.edits[1], { a: 3 });
  assert.equal(alignDraft(draft, [twin[0]]), null);
  assert.equal(alignDraft(draft, [...twin, file("inny.pdf", 1)]), null);
});

test("unsavedPositions: poprawki niepobrane do JSON-a ani ZIP-a", () => {
  const edits = [editedOdw(), structuredClone(results[1].data)];   // drugi dokument bez faktycznej zmiany
  assert.deepEqual(unsavedPositions({ results, edits }), [0]);
  assert.deepEqual(unsavedPositions({ results, edits, saved: [JSON.stringify(edits[0])] }), []);
  // po pobraniu kolejna poprawka znów jest niepobrana
  const later = structuredClone(edits[0]);
  later.OdwolanieKIO.data = "2025-10-14";
  assert.deepEqual(unsavedPositions({ results, edits: [later], saved: [JSON.stringify(edits[0])] }), [0]);
  assert.deepEqual(unsavedPositions({ results: null, edits }), []);
});

test("formatWhen i describeDraft: czytelny opis po polsku", () => {
  assert.equal(formatWhen(new Date(2026, 10, 21, 9, 7).getTime(), NOW), "dziś o 9:07");
  assert.equal(formatWhen(new Date(2026, 10, 20, 16, 30).getTime(), NOW), "wczoraj o 16:30");
  assert.equal(formatWhen(new Date(2026, 10, 18, 8, 0).getTime(), NOW), "18.11.2026 o 8:00");
  const draft = buildDraft({ files, results, edits: [editedOdw()], now: NOW });
  assert.equal(describeDraft(draft, NOW), "2 poprawki w 1 dokumencie (zapis: dziś o 17:05)");
  const many = { ...draft, changes: 5, docsEdited: 2 };
  assert.equal(describeDraft(many, NOW), "5 poprawek w 2 dokumentach (zapis: dziś o 17:05)");
  assert.equal(describeDraft({ ...draft, changes: 1 }, NOW), "1 poprawka w 1 dokumencie (zapis: dziś o 17:05)");
});
