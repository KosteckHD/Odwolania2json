// Spójność próbki atrapy (mock/extract-response.json) z opisem rubryk (fields.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { DOC_TYPES, getPath } from "../fields.js";

const fixture = JSON.parse(await readFile(new URL("../mock/extract-response.json", import.meta.url), "utf8"));
const okEntries = fixture.documents.filter((d) => d.status === "ok");

/** Ścieżki liści obiektu; tablice traktujemy jak wartość (np. lista „podpisujacy”). */
function leafPaths(value, prefix = "") {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return [prefix];
  return Object.entries(value).flatMap(([key, child]) => leafPaths(child, prefix ? `${prefix}.${key}` : key));
}

test("próbka ma wpisy ze wszystkimi trzema statusami", () => {
  const statuses = new Set(fixture.documents.map((d) => d.status));
  assert.deepEqual([...statuses].sort(), ["error", "ok", "unknown"]);
});

test("wpisy error mają kod i komunikat, unknown nie mają danych", () => {
  for (const doc of fixture.documents) {
    if (doc.status === "error") {
      assert.equal(typeof doc.error?.code, "string", doc.filename);
      assert.equal(typeof doc.error?.message, "string", doc.filename);
    }
    if (doc.status === "unknown") assert.equal(doc.data, null, doc.filename);
  }
});

test("wpisy ok mają typ opisany w DOC_TYPES", () => {
  assert.ok(okEntries.length > 0);
  for (const doc of okEntries) assert.ok(DOC_TYPES[doc.type], `brak typu ${doc.type} w fields.js`);
});

test("każde pole wpisu ok ma rubrykę w DOC_TYPES", () => {
  for (const doc of okEntries) {
    const { groups } = DOC_TYPES[doc.type];
    const groupPaths = groups.map((g) => g.path);
    for (const key of Object.keys(doc.data)) {
      assert.ok(groupPaths.includes(key), `${doc.filename}: grupa „${key}” bez opisu w fields.js`);
    }
    for (const group of groups) {
      const items = group.list ? doc.data[group.path] : [doc.data[group.path]];
      const keys = group.fields.map((f) => f.key);
      for (const item of items ?? []) {
        for (const leaf of leafPaths(item)) {
          assert.ok(keys.includes(leaf), `${doc.filename}: pole „${group.path}.${leaf}” bez rubryki`);
        }
      }
    }
  }
});

test("każda rubryka DOC_TYPES ma klucz we wpisie ok tego typu", () => {
  for (const doc of okEntries) {
    for (const group of DOC_TYPES[doc.type].groups) {
      const value = doc.data[group.path];
      assert.notEqual(value, undefined, `${doc.filename}: brak grupy „${group.path}”`);
      for (const item of group.list ? value : [value]) {
        for (const field of group.fields) {
          assert.notEqual(getPath(item, field.key), undefined, `${doc.filename}: brak „${group.path}.${field.key}”`);
        }
      }
    }
  }
});
