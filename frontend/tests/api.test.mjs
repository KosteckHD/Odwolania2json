// Testy klienta /api/extract i atrapy z api.js. Zamiast sieci podstawiamy fetchImpl.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  API_URL,
  ApiError,
  EMPTY_SELECTION_MESSAGE,
  buildForm,
  extractWithApi,
  extractWithMock,
  parseDocuments,
  pickMockEntry,
} from "../api.js";

const fixture = JSON.parse(await readFile(new URL("../mock/extract-response.json", import.meta.url), "utf8"));

const pdf = (name) => new File([`%PDF-1.4 ${name}`], name, { type: "application/pdf" });
const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

test("buildForm: każdy plik jako osobne pole files, w kolejności użytkownika", () => {
  const files = [pdf("odwolanie.pdf"), pdf("pelnomocnictwo.pdf"), pdf("odwolanie.pdf")];
  const form = buildForm(files);
  const entries = form.getAll("files");
  assert.equal(entries.length, 3);
  assert.deepEqual(entries.map((f) => f.name), ["odwolanie.pdf", "pelnomocnictwo.pdf", "odwolanie.pdf"]);
  assert.deepEqual([...form.keys()], ["files", "files", "files"]);
});

test("parseDocuments: poprawna odpowiedź zwraca listę wpisów", () => {
  const body = { documents: [{ status: "ok" }, { status: "unknown" }] };
  assert.equal(parseDocuments(body, 2), body.documents);
});

test("parseDocuments: zła liczba wpisów albo zły kształt → ApiError", () => {
  for (const body of [{ documents: [{}] }, { documents: {} }, {}, null]) {
    assert.throws(() => parseDocuments(body, 2), (e) => e instanceof ApiError && e.kind === "server");
  }
});

test("extractWithApi: 200 z trzema statusami", async () => {
  const files = [pdf("odwolanie.pdf"), pdf("ogloszenie.pdf"), pdf("skan.pdf")];
  const documents = [
    { filename: "odwolanie.pdf", status: "ok", type: "odwolanie", data: {} },
    { filename: "ogloszenie.pdf", status: "unknown", type: "unknown", data: null },
    { filename: "skan.pdf", status: "error", type: null, data: null, error: { code: "ocr_required", message: "Dokument wymaga odczytu OCR." } },
  ];
  let call;
  const fetchImpl = async (url, init) => {
    call = { url, init };
    return jsonResponse({ documents, meta: { model: "test" } });
  };

  const result = await extractWithApi(files, { fetchImpl });

  assert.equal(call.url, API_URL);
  assert.equal(call.init.method, "POST");
  assert.ok(call.init.body instanceof FormData);
  assert.deepEqual(call.init.body.getAll("files").map((f) => f.name), files.map((f) => f.name));
  assert.deepEqual(result.documents.map((d) => d.status), ["ok", "unknown", "error"]);
  assert.deepEqual(result.meta, { model: "test" });
});

test("extractWithApi: 200 bez meta → meta null", async () => {
  const fetchImpl = async () => jsonResponse({ documents: [{ status: "ok" }] });
  const result = await extractWithApi([pdf("a.pdf")], { fetchImpl });
  assert.equal(result.meta, null);
});

test("extractWithApi: 200 z inną liczbą wpisów niż plików → ApiError server", async () => {
  const fetchImpl = async () => jsonResponse({ documents: [{ status: "ok" }] });
  await assert.rejects(
    extractWithApi([pdf("a.pdf"), pdf("b.pdf")], { fetchImpl }),
    (e) => e instanceof ApiError && e.kind === "server",
  );
});

test("extractWithApi: 400 → ApiError invalid_request z komunikatem serwera", async () => {
  const fetchImpl = async () =>
    jsonResponse({ error: { code: "invalid_request", message: "Plik nie jest PDF-em." } }, 400);
  await assert.rejects(extractWithApi([pdf("a.pdf")], { fetchImpl }), (e) => {
    assert.ok(e instanceof ApiError);
    assert.equal(e.kind, "invalid_request");
    assert.equal(e.status, 400);
    assert.equal(e.message, "Plik nie jest PDF-em.");
    return true;
  });
});

test("extractWithApi: 400 bez treści JSON → domyślny komunikat", async () => {
  const fetchImpl = async () => new Response("Bad Request", { status: 400 });
  await assert.rejects(
    extractWithApi([pdf("a.pdf")], { fetchImpl }),
    (e) => e.kind === "invalid_request" && e.message === EMPTY_SELECTION_MESSAGE,
  );
});

test("extractWithApi: 500 → ApiError server z kodem HTTP w komunikacie", async () => {
  const fetchImpl = async () => jsonResponse({ error: { message: "Awaria modelu." } }, 500);
  await assert.rejects(extractWithApi([pdf("a.pdf")], { fetchImpl }), (e) => {
    assert.ok(e instanceof ApiError);
    assert.equal(e.kind, "server");
    assert.equal(e.status, 500);
    assert.equal(e.message, "Awaria modelu. (HTTP 500)");
    return true;
  });
});

test("extractWithApi: 502 z HTML zamiast JSON → ApiError server", async () => {
  const fetchImpl = async () => new Response("<html>Bad Gateway</html>", { status: 502 });
  await assert.rejects(
    extractWithApi([pdf("a.pdf")], { fetchImpl }),
    (e) => e.kind === "server" && e.status === 502 && e.message.endsWith("(HTTP 502)"),
  );
});

test("extractWithApi: błąd sieci → ApiError network", async () => {
  const fetchImpl = async () => {
    throw new TypeError("fetch failed");
  };
  await assert.rejects(
    extractWithApi([pdf("a.pdf")], { fetchImpl }),
    (e) => e instanceof ApiError && e.kind === "network" && e.status === null,
  );
});

test("extractWithApi: przerwanie (AbortError) przechodzi bez zmiany", async () => {
  const fetchImpl = async () => {
    throw new DOMException("Przerwano", "AbortError");
  };
  await assert.rejects(extractWithApi([pdf("a.pdf")], { fetchImpl }), { name: "AbortError" });
});

test("extractWithApi: pusta lista plików → invalid_request bez wywołania serwera", async () => {
  let called = false;
  const fetchImpl = async () => {
    called = true;
  };
  await assert.rejects(
    extractWithApi([], { fetchImpl }),
    (e) => e.kind === "invalid_request" && e.status === 400,
  );
  assert.equal(called, false);
});

test("pickMockEntry: dobór wpisu po nazwie pliku", () => {
  const docs = fixture.documents;
  const pick = (name, index = 0) => pickMockEntry(name, index, docs);
  assert.equal(pick("Odwolanie_KIO.pdf").type, "odwolanie");
  assert.equal(pick("pełnomocnictwo.pdf").type, "pelnomocnictwo");
  assert.equal(pick("potwierdzenie_przelewu.pdf").type, "przelew");
  assert.equal(pick("skan_pisma.pdf").status, "error");
  assert.equal(pick("ogloszenie_bzp.pdf").status, "unknown");
});

test("pickMockEntry: nieznana nazwa dostaje kolejny wpis po indeksie", () => {
  const docs = fixture.documents;
  assert.equal(pickMockEntry("plik.pdf", 1, docs), docs[1]);
  assert.equal(pickMockEntry("plik.pdf", docs.length + 2, docs), docs[2]);
});

test("extractWithMock: wpisy z próbki z nazwami wybranych plików", async (t) => {
  // atrapa czyta próbkę przez fetch(file://…), którego Node nie obsługuje: podstawiamy fetch
  t.mock.method(globalThis, "fetch", async () => jsonResponse(fixture));
  const files = [pdf("odwolanie.pdf"), pdf("skan_pisma.pdf")];
  const result = await extractWithMock(files, { delayMs: 0 });
  assert.deepEqual(result.documents.map((d) => d.filename), ["odwolanie.pdf", "skan_pisma.pdf"]);
  assert.deepEqual(result.documents.map((d) => d.status), ["ok", "error"]);
  // kopia, nie referencja do próbki
  result.documents[0].data.OdwolanieKIO.miejscowosc = "X";
  assert.notEqual(fixture.documents[0].data.OdwolanieKIO.miejscowosc, "X");
});
