// Klient POST /api/extract zgodny z docs/INTERFACES.md#api-dla-frontendu
// oraz atrapa oparta na kopii docs/fixtures/extract-response.json.

export const API_URL = "/api/extract";
export const TYPES_URL = "/api/document-types";
export const EMPTY_SELECTION_MESSAGE = "Wybierz co najmniej jeden plik PDF.";

/** Błąd całego żądania (nie pojedynczego dokumentu). */
export class ApiError extends Error {
  /**
   * @param {"invalid_request" | "server" | "network"} kind
   * @param {string} message
   * @param {number | null} status
   */
  constructor(kind, message, status = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

/** Buduje multipart: każdy PDF jako osobne pole `files`, w kolejności użytkownika. */
export function buildForm(files) {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  return form;
}

/** Sprawdza kształt odpowiedzi 200 i zwraca listę wpisów w kolejności plików. */
export function parseDocuments(body, expectedCount) {
  if (!body || !Array.isArray(body.documents) || body.documents.length !== expectedCount) {
    throw new ApiError("server", "Serwer zwrócił odpowiedź w nieoczekiwanym formacie.");
  }
  return body.documents;
}

/** Prawdziwe wywołanie backendu. */
export async function extractWithApi(files, { signal, fetchImpl = fetch } = {}) {
  if (files.length === 0) throw new ApiError("invalid_request", EMPTY_SELECTION_MESSAGE, 400);

  let response;
  try {
    response = await fetchImpl(API_URL, { method: "POST", body: buildForm(files), signal });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("network", "Brak połączenia z serwerem. Sprawdź, czy backend działa.");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (response.status === 400) {
    throw new ApiError("invalid_request", body?.error?.message ?? EMPTY_SELECTION_MESSAGE, 400);
  }
  if (!response.ok) {
    const detail = body?.error?.message ?? "Przetwarzanie sprawy nie powiodło się.";
    throw new ApiError("server", `${detail} (HTTP ${response.status})`, response.status);
  }
  // `meta` (np. { model }) jest opcjonalne: panel pokazuje je, jeśli backend je zwróci.
  return { documents: parseDocuments(body, files.length), meta: body.meta ?? null };
}

/** Lista typów z konfiguracji backendu (opcjonalny endpoint, patrz API-PROPOZYCJE.md). */
export async function fetchDocumentTypes({ fetchImpl = fetch } = {}) {
  const response = await fetchImpl(TYPES_URL);
  if (!response.ok) throw new ApiError("server", `HTTP ${response.status}`, response.status);
  const body = await response.json();
  if (!Array.isArray(body?.types)) throw new ApiError("server", "Nieoczekiwany format listy typów.");
  return body.types;
}

/** Dobiera wpis z próbki po nazwie pliku; nieznane nazwy dostają kolejne wpisy. */
export function pickMockEntry(fileName, index, documents) {
  const name = fileName.toLowerCase();
  const rules = [
    [/odwol/, (d) => d.type === "odwolanie"],
    [/pelnom|pełnom/, (d) => d.type === "pelnomocnictwo"],
    [/przelew|potwierdz/, (d) => d.type === "przelew"],
    [/skan|scan|ocr/, (d) => d.status === "error"],
    [/ogloszen|ogłoszen|bzp|ted|pismo/, (d) => d.status === "unknown"],
  ];
  for (const [pattern, match] of rules) {
    if (pattern.test(name)) {
      const found = documents.find(match);
      if (found) return found;
    }
  }
  return documents[index % documents.length];
}

// Pliki, które atrapa już raz zwróciła z błędem. Ponowna wysyłka tego samego
// pliku (np. „Ponów błędne”) się udaje, jak po chwilowej awarii OCR albo modelu.
const failedOnce = new WeakSet();

/** Atrapa: wpisy z próbki dla wybranych plików, z opóźnieniem jak przy LLM. */
export async function extractWithMock(files, { signal, delayMs = 1400 } = {}) {
  if (files.length === 0) throw new ApiError("invalid_request", EMPTY_SELECTION_MESSAGE, 400);

  const fixtureUrl = new URL("./mock/extract-response.json", import.meta.url);
  const fixture = await (await fetch(fixtureUrl, { signal })).json();
  await wait(delayMs, signal);

  const documents = files.map((file, index) => {
    let entry = pickMockEntry(file.name, index, fixture.documents);
    if (entry.status === "error") {
      if (failedOnce.has(file)) entry = retryEntry(fixture.documents) ?? entry;
      else failedOnce.add(file);
    }
    return { ...structuredClone(entry), filename: file.name };
  });
  return { documents, meta: null };
}

/** Wynik udanego ponowienia w atrapie: skan pełnomocnictwa odczytany przez OCR. */
const retryEntry = (documents) =>
  documents.find((d) => d.type === "pelnomocnictwo") ?? documents.find((d) => d.status === "ok");

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Przerwano", "AbortError"));
    }, { once: true });
  });
}
