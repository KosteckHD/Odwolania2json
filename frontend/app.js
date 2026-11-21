import { ApiError, extractWithApi, extractWithMock, fetchDocumentTypes } from "./api.js";
import { DOC_TYPES, getPath, typeLabel } from "./fields.js";
import { zipStore } from "./zip.js";
import { createPdfViewer } from "./pdfview.js";
import { expectedDigits, pickAmount, pickCode, pickDate, pickDigits, pickText } from "./parse.js";

const STATUS_TEXT = {
  selected: "Czeka na przetworzenie",
  pending: "Przetwarzanie…",
  unknown: "Nie rozpoznano",
  error: "Błąd",
};

const state = {
  mode: readMode(),
  view: "case",
  caseName: null,     // nazwa folderu sprawy, gdy wgrano folder
  files: [],          // File[] w kolejności wyboru
  urls: [],           // adresy podglądu PDF, równoległe do files
  results: null,      // wpisy odpowiedzi wyrównane po pozycji z `files`
  meta: null,         // opcjonalne informacje o przebiegu (model, czas)
  pending: false,
  requestError: null,
  selected: null,
  sheetMode: "fields",
  types: null,        // lista typów do widoku „Typy dokumentów”
  edits: [],          // dane po ręcznych poprawkach (po pozycji); brak = bez zmian
  active: null,       // rubryka z ostatnim fokusem: { index, path, field, apply(text) }
};

const viewers = new WeakMap(); // File → podgląd PDF (renderowany raz)

function readPref(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
state.showPdf = readPref("o2j-pdf", "1") === "1";
state.split = Math.min(72, Math.max(34, Number(readPref("o2j-split2", "48")) || 48));
state.pdfFull = false;

/** Przeciągany podział między rubrykami a PDF-em (też strzałkami z klawiatury). */
function splitter(body) {
  const bar = node("div", "splitter");
  bar.setAttribute("role", "separator");
  bar.setAttribute("aria-orientation", "vertical");
  bar.setAttribute("aria-label", "Zmień szerokość rubryk i podglądu PDF");
  bar.tabIndex = 0;
  const apply = (pct) => {
    state.split = Math.min(72, Math.max(34, Math.round(pct)));
    body.style.setProperty("--split", `${state.split}%`);
    bar.setAttribute("aria-valuenow", String(state.split));
    try { localStorage.setItem("o2j-split2", String(state.split)); } catch { /* bez pamięci */ }
  };
  bar.setAttribute("aria-valuemin", "34");
  bar.setAttribute("aria-valuemax", "72");
  bar.setAttribute("aria-valuenow", String(state.split));
  bar.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    bar.setPointerCapture(event.pointerId);
    const rect = body.getBoundingClientRect();
    const move = (e) => apply(((e.clientX - rect.left) / rect.width) * 100);
    const up = () => { bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up); };
    bar.addEventListener("pointermove", move);
    bar.addEventListener("pointerup", up);
  });
  bar.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") { event.preventDefault(); apply(state.split - 3); }
    if (event.key === "ArrowRight") { event.preventDefault(); apply(state.split + 3); }
  });
  return bar;
}

const $ = (id) => document.getElementById(id);
const el = {
  app: $("app"), rail: $("rail"), scrim: $("rail-scrim"),
  navToggle: $("nav-toggle"), navToggleLabel: $("nav-toggle-label"), menuBtn: $("menu-btn"),
  mode: $("mode-select"), modeFlag: $("mode-flag"), title: $("page-title"),
  steps: $("steps"), main: $("main"),
  viewCase: $("view-case"), viewHelp: $("view-help"), viewTypes: $("view-types"),
  form: $("upload-form"), drop: $("drop"), input: $("file-input"), folderInput: $("folder-input"),
  fileLabel: $("file-label"),
  list: $("file-list"), actions: $("actions"), submit: $("submit-btn"), note: $("actions-note"),
  message: $("request-message"), tally: $("tally"), sheet: $("sheet"),
  summary: $("summary"), downloadAll: $("download-all"), downloadAllLabel: $("download-all-label"),
  typesList: $("types-list"), typesSource: $("types-source"),
};

/* ---------- nawigacja ---------- */

const NAV_KEY = "o2j-nav";
const mobile = window.matchMedia("(max-width: 900px)");
const narrow = window.matchMedia("(max-width: 1180px)");

function setNav(collapsed) {
  el.app.dataset.nav = collapsed ? "collapsed" : "expanded";
  el.navToggle.setAttribute("aria-expanded", String(!collapsed));
  el.navToggleLabel.textContent = collapsed ? "Rozwiń menu" : "Zwiń menu";
  try { localStorage.setItem(NAV_KEY, collapsed ? "collapsed" : "expanded"); } catch { /* bez pamięci */ }
}
function setDrawer(open) {
  el.app.dataset.drawer = open ? "open" : "closed";
  el.menuBtn.setAttribute("aria-expanded", String(open));
  el.scrim.hidden = !open;
  if (open) el.rail.querySelector(".rail-item")?.focus();
}

let savedNav = null;
try { savedNav = localStorage.getItem(NAV_KEY); } catch { /* bez pamięci */ }
setNav(savedNav === "collapsed");
let navTouched = savedNav !== null;   // użytkownik sam wybrał stan menu
el.navToggle.addEventListener("click", () => {
  navTouched = true;
  setNav(el.app.dataset.nav !== "collapsed");
});
/** Po przetworzeniu na mniejszym ekranie zwijamy menu, żeby rubryki miały miejsce. */
function makeRoomForResults() {
  if (!navTouched && window.innerWidth < 1700 && !mobile.matches) {
    el.app.dataset.nav = "collapsed";
    el.navToggle.setAttribute("aria-expanded", "false");
    el.navToggleLabel.textContent = "Rozwiń menu";
  }
}
el.menuBtn.addEventListener("click", () => setDrawer(true));
el.scrim.addEventListener("click", () => setDrawer(false));

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    if (mobile.matches) setDrawer(false);
    if (state.view === "types") loadTypes();
    render();
    el.main.focus();
  });
});

$("new-case").addEventListener("click", () => {
  resetCase();
  state.view = "case";
  if (mobile.matches) setDrawer(false);
  render();
  el.main.focus();
});

function resetCase() {
  state.urls.forEach((u) => URL.revokeObjectURL(u));
  Object.assign(state, {
    caseName: null, files: [], urls: [], results: null, meta: null,
    requestError: null, selected: null, pending: false, edits: [], active: null,
  });
  el.input.value = "";
  el.folderInput.value = "";
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && el.app.dataset.drawer === "open") {
    setDrawer(false);
    el.menuBtn.focus();
    return;
  }
  // ↑/↓ przełączają dokument, gdy fokus jest na liście plików
  if ((event.key === "ArrowDown" || event.key === "ArrowUp") && event.target.closest?.(".file-list")) {
    if (!state.files.length) return;
    event.preventDefault();
    const next = Math.min(state.files.length - 1, Math.max(0, (state.selected ?? 0) + (event.key === "ArrowDown" ? 1 : -1)));
    selectDocument(next);
    el.list.querySelectorAll(".file-main")[next]?.focus();
  }
});

/* ---------- źródło wyników ---------- */

function readMode() {
  return new URLSearchParams(location.search).get("mock") === "1" ? "mock" : "api";
}
el.mode.value = state.mode;
el.mode.addEventListener("change", () => {
  state.mode = el.mode.value;
  state.types = null;
  const url = new URL(location.href);
  if (state.mode === "mock") url.searchParams.set("mock", "1");
  else url.searchParams.delete("mock");
  history.replaceState(null, "", url);
  if (state.view === "types") loadTypes();
  render();
});

/* ---------- wybór plików ---------- */

const isPdf = (file) => file.type === "application/pdf" || /\.pdf$/i.test(file.name);

function addFiles(fileList, caseName = null) {
  const incoming = [...fileList];
  const pdfs = incoming.filter(isPdf).sort((a, b) => (caseName ? a.name.localeCompare(b.name, "pl") : 0));
  const skipped = incoming.length - pdfs.length;
  if (state.results || caseName) resetCase();     // nowa partia albo folder = nowa sprawa
  if (caseName) state.caseName = caseName;
  state.files = [...state.files, ...pdfs];
  state.urls = [...state.urls, ...pdfs.map((f) => URL.createObjectURL(f))];
  state.results = null;
  state.requestError = skipped && !caseName
    ? `Pominięto ${skipped} ${skipped === 1 ? "plik, który nie jest" : "pliki, które nie są"} PDF-em.`
    : pdfs.length === 0 ? "W wybranym folderze nie ma plików PDF." : null;
  if (state.selected === null && state.files.length) state.selected = 0;
  render();
}

el.input.addEventListener("change", () => {
  addFiles(el.input.files);
  el.input.value = "";
});
el.folderInput.addEventListener("change", () => {
  const files = [...el.folderInput.files];
  const top = files[0]?.webkitRelativePath?.split("/")[0] || "sprawa";
  const direct = files.filter((f) => f.webkitRelativePath.split("/").length === 2);  // jak input/<sprawa>/
  addFiles(direct.length ? direct : files, top);
  el.folderInput.value = "";
});

["dragenter", "dragover"].forEach((type) =>
  el.drop.addEventListener(type, (event) => {
    event.preventDefault();
    if (!state.pending) el.drop.dataset.over = "true";
  }),
);
["dragleave", "drop"].forEach((type) =>
  el.drop.addEventListener(type, (event) => {
    event.preventDefault();
    el.drop.dataset.over = "false";
  }),
);
el.drop.addEventListener("drop", (event) => {
  if (!state.pending && event.dataTransfer?.files?.length) addFiles(event.dataTransfer.files);
});
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());

function removeFile(index) {
  state.files.splice(index, 1);
  URL.revokeObjectURL(state.urls[index]);
  state.urls.splice(index, 1);
  if (state.selected !== null) {
    if (state.files.length === 0) state.selected = null;
    else if (state.selected >= state.files.length) state.selected = state.files.length - 1;
  }
  render();
}

function selectDocument(index) {
  if (state.selected === index) return;
  state.selected = index;
  state.active = null;
  state.pdfFull = false;
  el.sheet.querySelectorAll(".pdfv-full").forEach((b) => b.setAttribute("aria-pressed", "false"));
  hideInsertButton();
  render();
}

/* ---------- wysyłka ---------- */

el.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.pending) return;
  if (state.files.length === 0) {
    state.requestError = "Wybierz co najmniej jeden plik PDF.";
    render();
    return;
  }
  Object.assign(state, { pending: true, requestError: null, results: null, meta: null, active: null });
  render();

  const extract = state.mode === "mock" ? extractWithMock : extractWithApi;
  const started = performance.now();
  const slowTimer = setTimeout(() => {
    el.note.textContent = "To trwa dłużej niż zwykle. Model wciąż czyta dokumenty.";
  }, 8000);
  try {
    const { documents, meta } = await extract(state.files);
    state.results = documents;
    state.edits = [];
    state.meta = { ...meta, seconds: (performance.now() - started) / 1000 };
    makeRoomForResults();
    const firstOk = documents.findIndex((r) => r.status === "ok");
    state.selected = firstOk >= 0 ? firstOk : 0;
  } catch (error) {
    state.requestError = error instanceof ApiError ? error.message : "Nieoczekiwany błąd aplikacji. Spróbuj ponownie.";
    if (!(error instanceof ApiError)) console.error(error);
  } finally {
    clearTimeout(slowTimer);
    state.pending = false;
    render();
  }
});

/* ---------- render ---------- */

function statusAt(index) {
  if (state.pending) return "pending";
  return state.results?.[index]?.status ?? "selected";
}

function render() {
  el.viewCase.hidden = state.view !== "case";
  el.viewHelp.hidden = state.view !== "help";
  el.viewTypes.hidden = state.view !== "types";
  el.app.dataset.view = state.view;
  document.querySelectorAll(".rail-item[data-view]").forEach((b) => {
    if (b.dataset.view === state.view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  el.modeFlag.hidden = state.mode !== "mock";
  el.title.textContent = state.caseName ? `Sprawa: ${state.caseName}` : "Sprawa odwoławcza";

  const step = state.results ? 3 : state.files.length ? 2 : 1;
  el.steps.querySelectorAll("li").forEach((li) => {
    const n = Number(li.dataset.step);
    li.dataset.state = n < step ? "done" : n === step ? "current" : "todo";
    if (n === step) li.setAttribute("aria-current", "step");
    else li.removeAttribute("aria-current");
  });

  el.input.disabled = state.pending;
  el.folderInput.disabled = state.pending;
  el.drop.dataset.compact = String(state.files.length > 0);
  el.drop.querySelector(".drop-title").textContent = state.files.length ? "Dodaj:" : "Przeciągnij tutaj pliki PDF";
  el.fileLabel.textContent = state.files.length ? "Pliki" : "Wybierz pliki z dysku";
  el.message.hidden = !state.requestError;
  el.message.textContent = state.requestError ?? "";
  el.actions.hidden = state.files.length === 0;
  el.submit.disabled = state.pending;
  el.submit.classList.toggle("btn-line", Boolean(state.results));
  const n = state.files.length;
  el.submit.textContent = state.pending
    ? "Przetwarzanie…"
    : state.results ? "Przetwórz ponownie" : `Przetwórz ${n} ${plural(n, "plik", "pliki", "plików")}`;
  el.note.textContent = state.pending ? "System rozpoznaje typ każdego dokumentu po treści i wyciąga dane." : "";

  renderList();
  renderSummary();
  renderSheet();
}

function renderList() {
  el.list.replaceChildren(...state.files.map(renderFileRow));
}

function renderFileRow(file, index) {
  const status = statusAt(index);
  const entry = state.results?.[index];
  const li = document.createElement("li");
  li.className = "file-row";
  li.dataset.current = String(index === state.selected);

  const pos = node("span", "file-pos", String(index + 1));
  pos.setAttribute("aria-hidden", "true");

  const main = document.createElement("button");
  main.type = "button";
  main.className = "file-main";
  main.setAttribute("aria-current", String(index === state.selected));
  main.addEventListener("click", () => {
    selectDocument(index);
    if (narrow.matches) el.sheet.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const meta = node("span", "file-meta");
  if (status !== "selected") meta.append(badgeFor(status, entry));
  if (entry?.status === "ok") {
    const c = completeness(entry, dataAt(index));
    if (c) meta.append(node("span", null, `${c.filled}/${c.total} pól`));
    if (countEdits(index)) meta.append(node("span", "file-edited", "poprawiony"));
  } else {
    meta.append(node("span", null, formatSize(file.size)));
  }
  main.append(node("span", "sr-only", `Pozycja ${index + 1}: `), node("span", "file-name", file.name), meta);
  li.append(pos, main);

  if (!state.results && !state.pending) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "file-remove";
    remove.setAttribute("aria-label", `Usuń ${file.name} z listy`);
    remove.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-close"/></svg>';
    remove.addEventListener("click", () => removeFile(index));
    li.append(remove);
  }
  return li;
}

function badgeFor(status, entry) {
  if (status === "ok") return node("span", "badge badge-ok", typeLabel(entry.type));
  return node("span", `badge badge-${status}`, STATUS_TEXT[status]);
}

/* ---------- podsumowanie sprawy ---------- */

function renderSummary() {
  el.summary.hidden = !state.results;
  if (!state.results) return;
  const byType = new Map();
  for (const r of state.results) if (r.status === "ok") byType.set(r.type, (byType.get(r.type) ?? 0) + 1);
  const order = [...Object.keys(DOC_TYPES), ...[...byType.keys()].filter((t) => !DOC_TYPES[t])];
  const rows = order.map((type) => [typeLabel(type), byType.get(type) ?? 0, !byType.get(type)]);
  const unknown = state.results.filter((r) => r.status === "unknown").length;
  const errors = state.results.filter((r) => r.status === "error").length;
  if (unknown) rows.push(["Nie rozpoznano", unknown, false]);
  if (errors) rows.push(["Błędy", errors, false]);
  const items = rows.map(([label, count, muted]) => {
    const div = node("div", muted ? "tally-muted" : null);
    div.append(node("dt", null, label), node("dd", null, String(count)));
    return div;
  });
  if (state.meta) {
    const info = [];
    if (state.meta.model) info.push(`model: ${state.meta.model}`);
    info.push(`${state.meta.seconds.toFixed(1).replace(".", ",")} s`);
    const div = node("div", "tally-meta");
    div.append(node("dt", null, "Przebieg"), node("dd", null, info.join(" · ")));
    items.push(div);
  }
  el.tally.replaceChildren(...items);

  const files = resultFiles();
  el.downloadAll.hidden = files.length === 0;
  el.downloadAllLabel.textContent = `Pobierz wyniki (ZIP, ${files.length} ${plural(files.length, "plik", "pliki", "plików")})`;
}

/** Pliki wynikowe jak w output/<sprawa>/: JSON dla rozpoznanych, pusty .json dla nierozpoznanych. */
function resultFiles() {
  if (!state.results) return [];
  const folder = safeName(state.caseName ?? "sprawa");
  const used = new Set();
  const files = [];
  state.results.forEach((r, i) => {
    if (r.status !== "ok" && r.status !== "unknown") return;   // błąd: brak pliku, jak w CLI
    let name = jsonName(state.files[i].name);
    for (let k = 2; used.has(name); k++) name = jsonName(state.files[i].name).replace(/\.json$/, ` (${k}).json`);
    used.add(name);
    files.push({ name: `${folder}/${name}`, text: r.status === "ok" ? `${JSON.stringify(dataAt(i), null, 2)}\n` : "" });
  });
  return files;
}

el.downloadAll.addEventListener("click", () => {
  const files = resultFiles();
  if (files.length) downloadBlob(`${safeName(state.caseName ?? "sprawa")}.zip`, zipStore(files));
});

/* ---------- arkusz ---------- */

function renderSheet() {
  const index = state.selected;
  const file = index !== null ? state.files[index] : null;

  if (!file) {
    el.sheet.dataset.layout = "guide";
    el.sheet.replaceChildren(emptyGuide());
    return;
  }

  const entry = state.results?.[index];
  const head = node("div", "sheet-head");
  const titleRow = node("div", "sheet-title-row");
  const title = node("h2", "sheet-title", file.name);
  title.id = "sheet-heading";
  titleRow.append(title);
  if (entry || state.pending) titleRow.append(badgeFor(statusAt(index), entry));
  head.append(titleRow);

  let left;
  if (state.pending) {
    left = node("div", "skeleton");
    left.setAttribute("aria-label", "Trwa przetwarzanie dokumentu");
    for (let i = 0; i < 8; i++) left.append(node("div"));
  } else if (!entry) {
    left = stateBlock("Plik czeka na przetworzenie",
      ["Dodaj pozostałe dokumenty sprawy i kliknij „Przetwórz”. Dane tego pliku pojawią się w tym miejscu."]);
  } else if (entry.status === "unknown") {
    left = stateBlock("Nie rozpoznano typu dokumentu", [
      "Treść pliku nie pasuje do odwołania, pełnomocnictwa ani potwierdzenia przelewu, więc nie wyciągnięto danych. W wynikach sprawy dostanie pusty plik JSON, zgodnie z formatem UZP.",
      "Jeśli to jednak jeden z tych dokumentów, sprawdź w podglądzie, czy PDF jest kompletny i czytelny.",
    ]);
  } else if (entry.status === "error") {
    left = stateBlock("Nie udało się przetworzyć pliku", [
      entry.error?.message ?? "Wystąpił błąd podczas odczytu dokumentu.",
      "Pozostałe pliki sprawy są dostępne. Ten plik nie trafi do wyników.",
    ]);
    if (entry.error?.code) left.append(node("p", "state-code", `Kod błędu: ${entry.error.code}`));
  } else {
    head.append(sheetTools(index, file), sheetInfo(index, entry));
    left = state.sheetMode === "json" ? jsonView(dataAt(index)) : fieldsView(index, entry);
  }

  const body = node("div", "sheet-body");
  const pane = node("div", "fields-pane");
  pane.append(left);
  body.dataset.pdf = String(state.showPdf);
  body.dataset.full = String(state.showPdf && state.pdfFull);
  body.style.setProperty("--split", `${state.split}%`);
  if (state.showPdf) body.append(pane, splitter(body), pdfPane(index));
  else body.append(pane);
  el.sheet.dataset.layout = "doc";
  el.sheet.replaceChildren(head, body);
}

function sheetTools(index, file) {
  const tools = node("div", "sheet-tools");
  const seg = node("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Widok danych");
  for (const [mode, label] of [["fields", "Pola"], ["json", "JSON"]]) {
    const b = node("button", null, label);
    b.type = "button";
    b.setAttribute("aria-pressed", String(state.sheetMode === mode));
    b.addEventListener("click", () => { state.sheetMode = mode; state.active = null; hideInsertButton(); renderSheet(); });
    seg.append(b);
  }
  const download = node("button", "btn");
  download.type = "button";
  download.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-download"/></svg>';
  download.append(`Pobierz ${jsonName(file.name)}`);
  download.addEventListener("click", () => downloadJson(file.name, dataAt(index)));
  const pdfToggle = node("button", "btn btn-line btn-toggle", "Podgląd PDF");
  pdfToggle.type = "button";
  pdfToggle.setAttribute("aria-pressed", String(state.showPdf));
  pdfToggle.addEventListener("click", () => {
    state.showPdf = !state.showPdf;
    try { localStorage.setItem("o2j-pdf", state.showPdf ? "1" : "0"); } catch { /* bez pamięci */ }
    renderSheet();
  });
  tools.append(seg, pdfToggle, download);
  return tools;
}

function sheetInfo(index, entry) {
  const info = node("p", "sheet-info");
  info.id = "sheet-info";
  fillSheetInfo(info, index, entry);
  return info;
}
function fillSheetInfo(info, index, entry) {
  const c = completeness(entry, dataAt(index));
  const edited = countEdits(index);
  const parts = [];
  if (c) parts.push(`Wypełniono ${c.filled} z ${c.total} pól`);
  if (edited) parts.push(`poprawiono ręcznie: ${edited}`);
  info.replaceChildren(parts.join(" · "));
  if (state.sheetMode === "fields") {
    info.append(node("span", "sheet-hint", "Wpisuj wprost w rubryki albo zaznacz tekst w PDF-ie."));
  }
}

/** Po wpisaniu wartości: odświeża liczniki bez przebudowy arkusza (fokus zostaje). */
function refreshAfterEdit(index) {
  const info = $("sheet-info");
  if (info) fillSheetInfo(info, index, state.results[index]);
  renderList();
  renderSummary();
}

function pdfPane(index) {
  const wrap = node("section", "pdf-pane");
  wrap.setAttribute("aria-label", "Podgląd PDF");
  const file = state.files[index];
  let viewer = viewers.get(file);
  if (!viewer) {
    viewer = createPdfViewer(file, state.urls[index], `Podgląd: ${file.name}`);
    viewers.set(file, viewer);
  }
  wrap.append(viewer.element);
  return wrap;
}

function emptyGuide() {
  const wrap = node("div", "state guide-wrap");
  const h = node("h2", "state-title", "Zacznij od wgrania dokumentów sprawy");
  h.id = "sheet-heading";
  wrap.append(h, node("p", null, "Panel odczyta każdy PDF, rozpozna jego typ po treści i przygotuje plik JSON w formacie Urzędu Zamówień Publicznych."));
  const guide = node("ol", "guide");
  [
    ["Wgraj PDF-y", "Przeciągnij pliki na pole „Dokumenty sprawy” albo wskaż cały folder sprawy."],
    ["Przetwórz", "Kliknij „Przetwórz”. Każdy plik dostanie swój status."],
    ["Sprawdź i pobierz", "Popraw dane wprost w rubrykach, porównując z PDF-em obok, i pobierz JSON-y sprawy."],
  ].forEach(([t, text], i) => {
    const li = node("li");
    const no = node("span", "guide-no", String(i + 1));
    no.setAttribute("aria-hidden", "true");
    const box = node("div", "guide-text");
    box.append(node("strong", null, t), node("span", null, text));
    li.append(no, box);
    guide.append(li);
  });
  wrap.append(guide);
  return wrap;
}

function stateBlock(title, paragraphs) {
  const wrap = node("div", "state");
  wrap.append(node("h3", "state-title", title), ...paragraphs.map((p) => node("p", null, p)));
  return wrap;
}

/* ---------- dane i poprawki ---------- */

function dataAt(index) {
  return state.edits[index] ?? state.results?.[index]?.data ?? null;
}

function completeness(entry, data = entry.data) {
  const spec = DOC_TYPES[entry.type];
  if (!spec || !data) return null;
  let filled = 0, total = 0;
  for (const group of spec.groups) {
    const value = data[group.path];
    const items = group.list ? (Array.isArray(value) && value.length ? value : [{}]) : [value];
    for (const item of items) for (const f of group.fields) {
      total += 1;
      if (!isEmptyValue(getPath(item, f.key))) filled += 1;
    }
  }
  return { filled, total };
}

const isEmptyValue = (v) => v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);

function countEdits(index) {
  const edited = state.edits[index];
  if (!edited) return 0;
  let n = 0;
  const walk = (a, b) => {
    if (a && typeof a === "object") {
      new Set([...Object.keys(a), ...Object.keys(b && typeof b === "object" ? b : {})]).forEach((k) => walk(a[k], b?.[k]));
    } else if (JSON.stringify(a ?? null) !== JSON.stringify(b ?? null)) n += 1;
  };
  walk(edited, state.results[index].data);
  return n;
}

function isEdited(index, path) {
  if (!state.edits[index]) return false;
  return JSON.stringify(getPath(state.edits[index], path) ?? null)
    !== JSON.stringify(getPath(state.results[index].data, path) ?? null);
}

function setValue(index, path, value) {
  const data = state.edits[index] ?? structuredClone(state.results[index].data);
  const keys = path.split(".");
  let target = data;
  keys.slice(0, -1).forEach((key, i) => {
    if (target[key] == null || typeof target[key] !== "object") target[key] = /^\d+$/.test(keys[i + 1]) ? [] : {};
    target = target[key];
  });
  target[keys.at(-1)] = value;
  state.edits[index] = data;
}

function evidenceMap(entry) {
  const map = new Map();
  for (const ev of entry.evidence ?? []) {
    if (!ev?.field_path) continue;
    map.set(ev.field_path, [ev.page_number && `str. ${ev.page_number}`, ev.method].filter(Boolean).join(" · "));
  }
  return map;
}

/* ---------- rubryki do wpisywania ---------- */

function fieldsView(index, entry) {
  const spec = DOC_TYPES[entry.type];
  const data = dataAt(index);
  const wrap = node("div", "fields-view");
  const ctx = { n: 0, evidence: evidenceMap(entry), index };
  if (!spec) {
    wrap.append(genericGroup(typeLabel(entry.type), data, ctx));
    return wrap;
  }
  for (const group of spec.groups) {
    const value = data?.[group.path];
    if (group.list) {
      // pusta lista: pokazujemy puste rubryki pierwszej pozycji, żeby dało się je uzupełnić
      const items = Array.isArray(value) && value.length ? value : [{}];
      items.forEach((item, i) => {
        const title = items.length > 1 ? `${group.title} ${i + 1}` : group.title;
        wrap.append(groupBlock(title, group.fields.map((f) =>
          fieldBlock(f, getPath(item, f.key), ctx, `${group.path}.${i}.${f.key}`))));
      });
    } else {
      wrap.append(groupBlock(group.title, group.fields.map((f) =>
        fieldBlock(f, getPath(value, f.key), ctx, `${group.path}.${f.key}`))));
    }
  }
  return wrap;
}

function groupBlock(title, children) {
  const section = node("section", "group");
  section.append(node("h3", "group-title", title));
  const grid = node("div", "fields");
  grid.append(...children);
  section.append(grid);
  return section;
}

function fieldBlock(field, value, ctx, path) {
  ctx.n += 1;
  const index = ctx.index;
  const wrap = node("div", `field field-${field.kind ?? "text"}${field.wide ? " field-wide" : ""}`);
  const id = `f-${index}-${path.replace(/[^\w]/g, "_")}`;
  const label = node("label", "field-label");
  label.htmlFor = id;
  label.append(node("span", "field-no", `${ctx.n}.`), field.label);
  const tags = node("span", "field-tags");
  label.append(tags);
  const error = node("p", "field-error");
  error.hidden = true;

  const updateTags = () => {
    tags.replaceChildren();
    const current = getPath(dataAt(index), path);
    if (isEdited(index, path)) {
      tags.append(node("span", "field-edited", "poprawione"));
      const undo = node("button", "link-btn", "cofnij");
      undo.type = "button";
      undo.addEventListener("click", (event) => {
        event.preventDefault();
        setValue(index, path, structuredClone(getPath(state.results[index].data, path) ?? null));
        renderSheet();
        refreshAfterEdit(index);
      });
      tags.append(undo);
    } else if (isEmptyValue(current)) {
      tags.append(node("span", "field-note", "brak w dokumencie"));
    } else {
      const source = ctx.evidence.get(path);
      if (source) tags.append(node("span", "field-source", source));
    }
  };

  /** Zapis wartości (lub błąd walidacji) z pola edycji. */
  // problem = błąd (wartość nie jest zapisywana); warn = ostrzeżenie (wartość zapisana)
  const commit = (value, problem = null, warn = false) => {
    error.hidden = !problem;
    error.textContent = problem ?? "";
    error.dataset.kind = warn ? "warn" : "error";
    wrap.dataset.invalid = String(Boolean(problem) && !warn);
    if (problem && !warn) return;
    setValue(index, path, value);
    updateTags();
    refreshAfterEdit(index);
  };

  const control = controlFor(field, value, id, commit, path);
  wrap.append(label, control.element, error);
  const activate = () => {
    if (state.active?.path === path && state.active.index === index) return;
    state.active = { index, path, field, apply: control.apply };
    el.sheet.querySelectorAll(".field[data-active]").forEach((f) => f.removeAttribute("data-active"));
    wrap.dataset.active = "true";
  };
  ["focusin", "pointerdown", "input"].forEach((t) => wrap.addEventListener(t, activate));
  updateTags();
  return wrap;
}

/**
 * Tworzy kontrolkę rubryki. Zwraca element oraz `apply(text)`, które wstawia
 * tekst zaznaczony w PDF-ie (z wyłuskaniem samej wartości) i zapisuje.
 */
function controlFor(field, value, id, commit, path) {
  switch (field.kind) {
    case "digits": case "account": case "code": return cellControl(field, value, id, commit, path);
    case "date": return dateControl(value, id, commit);
    case "bool": return choiceControl([["1", "tak", 1], ["0", "nie", 0], ["", "brak informacji", null]], value === true ? 1 : value === false ? 0 : value ?? null, id, commit, field.label);
    case "enum": return choiceControl([...Object.entries(field.labels ?? {}).map(([v, t]) => [v, t, v]), ["", "brak informacji", null]], value ?? null, id, commit, field.label);
    case "names": return namesControl(value, id, commit);
    case "amount": return amountControl(value, id, commit);
    default: return textControl(field, value, id, commit);
  }
}

/**
 * Kratki do wpisywania: niewidoczne pole tekstowe nad rzędem komórek.
 * Każda cyfra trafia do swojej kratki, bieżąca kratka jest podświetlona.
 */
function cellsBox(input, cellsCount, gaps = []) {
  const box = node("div", "cells-box");
  const row = node("div", "cells-row");
  row.setAttribute("aria-hidden", "true");
  box.append(row, input);
  const paint = () => {
    const chars = [...input.value];
    const count = Math.max(cellsCount(), chars.length);
    const caret = document.activeElement === input ? Math.min(input.selectionStart ?? chars.length, count - 1) : -1;
    const cells = [];
    for (let i = 0; i < count; i++) {
      if (gaps.includes(i)) cells.push(node("span", "cells-gap"));
      const c = node("i", null, chars[i] ?? "");
      if (!chars[i]) c.className = "is-empty";
      if (i === caret) c.classList.add("is-caret");
      cells.push(c);
    }
    row.replaceChildren(...cells);
    box.dataset.empty = String(chars.length === 0);
  };
  ["input", "focus", "keyup", "click", "select"].forEach((t) => input.addEventListener(t, paint));
  input.addEventListener("blur", () => setTimeout(paint));
  box.addEventListener("mousedown", (event) => {
    if (event.target === input) return;
    event.preventDefault();
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    paint();
  });
  paint();
  return { box, paint };
}

function cellControl(field, value, id, commit, path) {
  const lengths = field.kind === "code" ? [2] : expectedDigits(path);
  const input = document.createElement("input");
  input.id = id;
  input.className = "cells-input";
  input.inputMode = "numeric";
  input.autocomplete = "off";
  input.spellcheck = false;
  const max = field.kind === "code" ? 2 : Math.max(...(lengths.length ? lengths : [14]));
  input.maxLength = max;
  input.value = value == null ? "" : field.kind === "code" ? String(value).padStart(2, "0") : String(value).replace(/\D/g, "");
  const gaps = field.kind === "account" && lengths.includes(26) ? [2, 6, 10, 14, 18, 22] : [];
  const { box, paint } = cellsBox(input, () => (field.kind === "code" ? 2 : lengths[0] ?? 10), gaps);
  if (field.kind === "account") box.classList.add("cells-sm");
  const save = () => {
    const digits = input.value.replace(/\D/g, "");
    if (digits !== input.value) { input.value = digits; paint(); }
    if (!digits) return commit(null);
    if (field.kind === "code") {
      const n = Number(digits);
      return n >= 1 && n <= 12 ? commit(n) : commit(null, "Kod powodu to liczba od 1 do 12.");
    }
    commit(field.integer ? Number(digits) : digits);
  };
  input.addEventListener("input", save);
  input.addEventListener("blur", () => {
    const d = input.value;
    if (d && lengths.length && !lengths.includes(d.length)) {
      commit(field.integer ? Number(d) : d, `Sprawdź: zwykle ${lengths.join(" lub ")} cyfr, wpisano ${d.length}.`, true);
    }
  });
  return {
    element: box,
    apply(textFromPdf) {
      const code = pickCode(textFromPdf);
      const digits = field.kind === "code" ? (code ? String(code).padStart(2, "0") : "") : pickDigits(textFromPdf, lengths);
      input.value = digits.slice(0, max);
      save();
      input.focus();
      paint();
    },
  };
}

/** Data w trzech grupach kratek: RRRR MM DD. */
function dateControl(value, id, commit) {
  const wrap = node("div", "date-in");
  const m = String(value ?? "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const painters = [];
  const boxes = [];
  const parts = [["y", 4, "rok"], ["m", 2, "miesiąc"], ["d", 2, "dzień"]].map(([key, len, label], i) => {
    const input = document.createElement("input");
    if (i === 0) input.id = id;
    input.className = "cells-input";
    input.inputMode = "numeric";
    input.autocomplete = "off";
    input.maxLength = len;
    input.setAttribute("aria-label", label);
    input.value = m ? m[i + 1] : "";
    input.dataset.key = key;
    const { box, paint } = cellsBox(input, () => len);
    painters.push(paint);
    boxes.push(box);
    return input;
  });
  const save = () => {
    const [y, mo, d] = parts.map((p) => p.value);
    if (!y && !mo && !d) return commit(null);
    if (y.length === 4 && mo.length === 2 && d.length === 2) {
      const iso = pickDate(`${y}-${mo}-${d}`);
      return iso ? commit(iso) : commit(null, "Nieprawidłowy miesiąc albo dzień.");
    }
    commit(null, "Uzupełnij datę: rok, miesiąc i dzień.");
  };
  parts.forEach((input, i) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "");
      if (input.value.length === input.maxLength && parts[i + 1]) parts[i + 1].focus();
      save();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value && parts[i - 1]) parts[i - 1].focus();
    });
  });
  wrap.append(boxes[0], node("span", "date-sep"), boxes[1], node("span", "date-sep"), boxes[2]);
  return {
    element: wrap,
    apply(text) {
      const iso = pickDate(text);
      if (!iso) return commit(null, "W zaznaczeniu nie ma daty.");
      const [y, mo, d] = iso.split("-");
      parts[0].value = y; parts[1].value = mo; parts[2].value = d;
      save();
      parts[2].focus();
      painters.forEach((p) => p());
    },
  };
}

/** Wybór krzyżykiem: tak / nie / brak informacji (radio). */
function choiceControl(options, value, id, commit, label) {
  const group = node("div", "choices");
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", label);
  const name = `${id}-r`;
  options.forEach(([v, text, stored], i) => {
    const lab = node("label", "choice");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = v;
    if (i === 0) input.id = id;
    input.checked = stored === value || (stored === null && value == null);
    input.addEventListener("change", () => commit(stored));
    const box = node("span", "choice-box");
    box.setAttribute("aria-hidden", "true");
    lab.append(input, box, text);
    group.append(lab);
  });
  return { element: group, apply: () => commit(value, "Tę rubrykę zaznacz krzyżykiem.") };
}

function textControl(field, value, id, commit) {
  const multi = field.wide;
  const input = document.createElement(multi ? "textarea" : "input");
  input.id = id;
  input.className = "box-in";
  if (multi) input.rows = 1;
  input.value = value ?? "";
  const grow = () => {
    if (!multi) return;
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight + 2}px`;
  };
  requestAnimationFrame(grow);
  // szerokość kolumny zmienia się (zwijanie menu, przeciąganie podziału, fonty): wysokość za nią
  if (multi) {
    let lastWidth = 0;
    new ResizeObserver(([e]) => {
      const w = Math.round(e.contentRect.width);
      if (w !== lastWidth) { lastWidth = w; grow(); }
    }).observe(input);
    document.fonts?.ready.then(grow);
  }
  input.addEventListener("input", () => {
    grow();
    const t = input.value.replace(/\s+/g, " ").trim();
    commit(t || null);
  });
  if (multi) input.addEventListener("keydown", (event) => { if (event.key === "Enter") event.preventDefault(); });
  return {
    element: input,
    apply(text) {
      input.value = pickText(text);
      grow();
      commit(input.value || null);
      input.focus();
    },
  };
}

function amountControl(value, id, commit) {
  const wrap = node("div", "amount-in");
  const input = document.createElement("input");
  input.id = id;
  input.className = "box-in";
  input.inputMode = "decimal";
  input.value = value == null ? "" : Number(value).toLocaleString("pl-PL", { minimumFractionDigits: 2 });
  const save = () => {
    if (!input.value.trim()) return commit(null);
    const n = pickAmount(input.value);
    return n === null ? commit(null, "Wpisz kwotę, np. 10 000,00.") : commit(n);
  };
  input.addEventListener("input", save);
  input.addEventListener("blur", () => {
    const n = pickAmount(input.value);
    if (n !== null) input.value = n.toLocaleString("pl-PL", { minimumFractionDigits: 2 });
  });
  wrap.append(input, node("span", "amount-unit", "zł"));
  return {
    element: wrap,
    apply(text) {
      const n = pickAmount(text);
      if (n === null) return commit(null, "W zaznaczeniu nie ma kwoty.");
      input.value = n.toLocaleString("pl-PL", { minimumFractionDigits: 2 });
      commit(n);
      input.focus();
    },
  };
}

function namesControl(value, id, commit) {
  const input = document.createElement("textarea");
  input.id = id;
  input.className = "box-in";
  input.rows = Math.max(1, (value ?? []).length);
  input.placeholder = "jedna osoba w wierszu";
  input.value = (value ?? []).map((p) => p?.imie_nazwisko ?? "").join("\n");
  const save = () => {
    const list = input.value.split("\n").map((s) => s.trim()).filter(Boolean);
    input.rows = Math.max(1, input.value.split("\n").length);
    commit(list.map((imie_nazwisko) => ({ imie_nazwisko })));
  };
  input.addEventListener("input", save);
  return {
    element: input,
    apply(text) {
      const name = pickText(text);
      input.value = input.value.trim() ? `${input.value.trim()}\n${name}` : name;
      save();
      input.focus();
    },
  };
}

function genericGroup(title, data, ctx) {
  const fields = [];
  const walk = (value, path) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.entries(value).forEach(([k, v]) => walk(v, path ? `${path}.${k}` : k));
    } else if (Array.isArray(value) && value.some((v) => v && typeof v === "object")) {
      value.forEach((v, i) => walk(v, `${path}.${i}`));
    } else {
      fields.push(fieldBlock({ label: path, kind: "text" }, Array.isArray(value) ? value.join(", ") : value, ctx, path));
    }
  };
  walk(data, "");
  return groupBlock(title, fields);
}

/* ---------- wstawianie zaznaczenia z PDF-u ---------- */

const insertBtn = node("button", "insert-btn");
insertBtn.type = "button";
insertBtn.hidden = true;
document.body.append(insertBtn);
let pendingSelection = "";

function hideInsertButton() {
  insertBtn.hidden = true;
  pendingSelection = "";
}

document.addEventListener("mouseup", (event) => {
  if (event.target === insertBtn) return;
  const inPdf = event.target.closest?.(".pdfv-stage");
  const selection = window.getSelection();
  const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
  if (!inPdf || !text) { hideInsertButton(); return; }
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  const ready = state.active && state.active.index === state.selected && state.sheetMode === "fields";
  pendingSelection = text;
  insertBtn.textContent = ready ? `Wstaw do: ${state.active.field.label}` : "Najpierw kliknij rubrykę po lewej";
  insertBtn.disabled = !ready;
  insertBtn.style.left = `${Math.min(window.innerWidth - 270, Math.max(8, rect.left))}px`;
  insertBtn.style.top = `${Math.min(window.innerHeight - 48, rect.bottom + 8)}px`;
  insertBtn.hidden = false;
});
insertBtn.addEventListener("mousedown", (event) => event.preventDefault());   // nie gubimy zaznaczenia
insertBtn.addEventListener("click", () => {
  if (!state.active || !pendingSelection) return;
  state.active.apply(pendingSelection);
  window.getSelection()?.removeAllRanges();
  hideInsertButton();
});
document.addEventListener("scroll", hideInsertButton, true);

/* ---------- typy dokumentów ---------- */

async function loadTypes() {
  if (state.types) return renderTypes();
  el.typesSource.textContent = "Wczytywanie listy typów…";
  el.typesList.replaceChildren();
  const local = Object.entries(DOC_TYPES).map(([id, t]) => ({
    doc_type: id, label: t.label,
    fields: t.groups.flatMap((g) => g.fields.map((f) => `${g.title}: ${f.label}`)),
  }));
  if (state.mode === "mock") {
    state.types = { list: local, source: "Dane przykładowe: typy znane panelowi." };
  } else {
    try {
      state.types = { list: await fetchDocumentTypes(), source: "Lista z konfiguracji backendu (configs/documents)." };
    } catch {
      state.types = { list: local, source: "Backend nie udostępnia jeszcze listy typów (GET /api/document-types), więc pokazuję typy znane panelowi." };
    }
  }
  renderTypes();
}

function renderTypes() {
  el.typesSource.textContent = state.types.source;
  el.typesList.replaceChildren(...state.types.list.map((t) => {
    const card = node("section", "type-row");
    const head = node("div", "type-head");
    head.append(node("h3", null, t.label ?? typeLabel(t.doc_type)), node("code", null, `${t.doc_type}.yaml`));
    const count = (t.fields ?? []).length;
    card.append(head, node("p", "type-meta", `${count} ${plural(count, "pole", "pola", "pól")} w schemacie`));
    if (count) {
      const ul = node("ul", "type-fields");
      t.fields.forEach((f) => ul.append(node("li", null, typeof f === "string" ? f : f.label ?? f.name ?? String(f))));
      card.append(ul);
    }
    return card;
  }));
}

/* ---------- JSON i pobieranie ---------- */

function jsonView(data) {
  const pre = node("pre", "json");
  pre.tabIndex = 0;
  pre.setAttribute("aria-label", "Dane dokumentu w formacie JSON");
  JSON.stringify(data, null, 2).split(/("(?:[^"\\]|\\.)*"(?=\s*:)|\bnull\b)/g).forEach((part) => {
    if (/^".*"$/.test(part)) pre.append(node("span", "k", part));
    else if (part === "null") pre.append(node("span", "n", part));
    else pre.append(part);
  });
  return pre;
}

const jsonName = (fileName) => `${fileName.replace(/\.pdf$/i, "")}.json`;
const safeName = (name) => name.replace(/[\\/:*?"<>|]+/g, "_").trim() || "sprawa";

function downloadJson(fileName, data) {
  downloadBlob(jsonName(fileName), new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json" }));
}
function downloadBlob(name, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- pomocnicze ---------- */

function node(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}
function plural(n, one, few, many) {
  if (n === 1) return one;
  const d = n % 10, t = n % 100;
  return d >= 2 && d <= 4 && (t < 12 || t > 14) ? few : many;
}
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

render();

/* powiększenie podglądu PDF na cały obszar arkusza (Esc wraca) */
document.addEventListener("pdf-full", (event) => {
  state.pdfFull = event.detail;
  const body = el.sheet.querySelector(".sheet-body");
  if (body) body.dataset.full = String(state.pdfFull);
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !state.pdfFull) return;
  state.pdfFull = false;
  const body = el.sheet.querySelector(".sheet-body");
  if (body) body.dataset.full = "false";
  el.sheet.querySelector('.pdfv-full')?.setAttribute("aria-pressed", "false");
});
