// Testy kolejki „plik po pliku” (extractEach w api.js): limit równoległości, kolejność, błąd jednego pliku, anulowanie.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ApiError, EXTRACT_CONCURRENCY, extractEach, extractWithApi } from "../api.js";

const pdf = (name) => new File([`%PDF-1.4 ${name}`], name, { type: "application/pdf" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const okEntry = (name) => ({ filename: name, status: "ok", type: "odwolanie", data: { n: name } });

/** Atrapa jednego żądania: czas zależny od pliku, liczy, ile żądań trwa naraz. */
function fakeExtract(delays, { fail = new Set() } = {}) {
  const stats = { active: 0, max: 0, started: [] };
  const extractOne = async (file, { signal } = {}) => {
    stats.active += 1;
    stats.max = Math.max(stats.max, stats.active);
    stats.started.push(file.name);
    try {
      await new Promise((resolve, reject) => {
        const t = setTimeout(resolve, delays[file.name] ?? 10);
        signal?.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("Przerwano", "AbortError")); }, { once: true });
      });
      if (fail.has(file.name)) throw new ApiError("server", "Przetwarzanie sprawy nie powiodło się. (HTTP 502)", 502);
      return { documents: [okEntry(file.name)], meta: { model: "test-model" } };
    } finally {
      stats.active -= 1;
    }
  };
  return { extractOne, stats };
}

test("domyślnie najwyżej 2 żądania naraz, każdy plik osobno", async () => {
  assert.equal(EXTRACT_CONCURRENCY, 2);
  const files = ["a", "b", "c", "d", "e"].map((n) => pdf(`${n}.pdf`));
  const { extractOne, stats } = fakeExtract({ "a.pdf": 30, "b.pdf": 10, "c.pdf": 20, "d.pdf": 5, "e.pdf": 5 });
  const out = await extractEach(files, { extractOne });
  assert.equal(stats.max, 2);
  assert.equal(stats.started.length, 5);
  assert.equal(out.aborted, false);
  assert.equal(out.meta.model, "test-model");
});

test("wyniki od razu po nadejściu, ale w documents w kolejności plików", async () => {
  const files = ["a", "b", "c"].map((n) => pdf(`${n}.pdf`));
  const { extractOne } = fakeExtract({ "a.pdf": 40, "b.pdf": 5, "c.pdf": 5 });
  const arrived = [];
  const out = await extractEach(files, { extractOne, onResult: (i, entry) => arrived.push([i, entry.filename]) });
  assert.deepEqual(arrived.map(([i]) => i), [1, 2, 0]);          // b i c gotowe przed długim a
  assert.deepEqual(out.documents.map((d) => d.filename), ["a.pdf", "b.pdf", "c.pdf"]);
});

test("limit równoległości da się zmienić", async () => {
  const files = ["a", "b", "c", "d"].map((n) => pdf(`${n}.pdf`));
  const one = fakeExtract({});
  await extractEach(files, { extractOne: one.extractOne, concurrency: 1 });
  assert.equal(one.stats.max, 1);
  const three = fakeExtract({});
  await extractEach(files, { extractOne: three.extractOne, concurrency: 3 });
  assert.equal(three.stats.max, 3);
});

test("błąd jednego pliku (HTTP 502) nie zatrzymuje pozostałych: plik dostaje status error", async () => {
  const files = ["a", "b", "c"].map((n) => pdf(`${n}.pdf`));
  const { extractOne } = fakeExtract({}, { fail: new Set(["b.pdf"]) });
  const out = await extractEach(files, { extractOne });
  assert.deepEqual(out.documents.map((d) => d.status), ["ok", "error", "ok"]);
  assert.equal(out.documents[1].filename, "b.pdf");
  assert.equal(out.documents[1].error.code, "http_502");
  assert.match(out.documents[1].error.message, /HTTP 502/);
});

test("błąd sieci przy prawdziwym kliencie: kod network_error tylko dla tego pliku", async () => {
  const files = [pdf("a.pdf"), pdf("b.pdf")];
  let call = 0;
  const fetchImpl = async () => {
    call += 1;
    if (call === 1) throw new TypeError("Failed to fetch");
    return new Response(JSON.stringify({ documents: [okEntry("b.pdf")], meta: { model: "m" } }), { status: 200 });
  };
  const out = await extractEach(files, { concurrency: 1, extractOne: (file, opts) => extractWithApi([file], { ...opts, fetchImpl }) });
  assert.equal(out.documents[0].status, "error");
  assert.equal(out.documents[0].error.code, "network_error");
  assert.equal(out.documents[1].status, "ok");
  assert.equal(out.meta.model, "m");
});

test("anulowanie zatrzymuje kolejkę i trwające żądania; gotowe wyniki zostają", async () => {
  const files = ["a", "b", "c", "d"].map((n) => pdf(`${n}.pdf`));
  const { extractOne, stats } = fakeExtract({ "a.pdf": 5, "b.pdf": 200, "c.pdf": 200, "d.pdf": 5 });
  const controller = new AbortController();
  const arrived = [];
  const run = extractEach(files, { extractOne, signal: controller.signal, onResult: (i) => arrived.push(i) });
  await sleep(60);                       // a gotowe, b i c w trakcie
  controller.abort();
  const out = await run;
  assert.equal(out.aborted, true);
  assert.deepEqual(arrived, [0]);
  assert.equal(out.documents[0].status, "ok");
  assert.deepEqual(out.documents.slice(1), [null, null, null]);
  assert.ok(!stats.started.includes("d.pdf"), "d nie powinien wystartować po anulowaniu");
  assert.equal(stats.active, 0);
});
