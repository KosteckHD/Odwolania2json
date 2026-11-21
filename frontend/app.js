import { extractEach, extractWithApi, extractWithMock, fetchDocumentTypes } from "./api.js";
import { DOC_TYPES, emptyListItem, getPath, typeLabel } from "./fields.js";
import { zipStore } from "./zip.js";
import { buildResultFiles, jsonName, retypeEntry, safeName } from "./export.js";
import { createPdfViewer } from "./pdfview.js";
import { STATUS, docsSummary, insertPlacement, positionText, progressText } from "./layout.js";
import { CHECKSUM_WARNING, checksumValid, expectedDigits, pickAmount, pickCode, pickDate, pickDigits, pickText } from "./parse.js";
import {
  DRAFT_STORAGE_KEY, alignDraft, buildDraft, caseKey, countChanges, describeDraft, findDraft,
  parseStore, plural, putDraft, unsavedPositions,
} from "./draft.js";


const state = {
  mode: readMode(),
  view: "case",
  caseName: null,     // nazwa folderu sprawy, gdy wgrano folder
  files: [],          // File[] w kolejności wyboru
  urls: [],           // adresy podglądu PDF, równoległe do files
  results: null,      // wpisy odpowiedzi wyrównane po pozycji z `files`
  meta: null,         // opcjonalne informacje o przebiegu (model, czas)
  pending: false,
  pendingSet: null,   // pozycje w trakcie ponawiania (null = wszystkie pliki)
  abort: null,        // AbortController bieżącej wysyłki
  slow: false,        // wysyłka trwa dłużej niż zwykle
  notice: null,       // komunikat nad listą: { kind: "error" | "info", text, retry }
  lastRun: null,      // pozycje nieudanej wysyłki do „Spróbuj ponownie” (null = wszystkie)
  selected: null,
  sheetMode: "fields",
  types: null,        // lista typów do widoku „Typy dokumentów”
  edits: [],          // dane po ręcznych poprawkach (po pozycji); brak = bez zmian
  active: null,       // rubryka z ostatnim fokusem: { index, path, field, apply(text) }
  saved: [],          // JSON danych z chwili ostatniego pobrania (po pozycji): do ostrzeżenia przed wyjściem
  restore: null,      // kopia robocza tej samej sprawy z pamięci przeglądarki, czeka na decyzję
  confirmRerun: false,   // „Przetwórz ponownie” czeka na drugie kliknięcie (są poprawki)
  confirmDocRetry: null, // „Przetwórz ten plik ponownie” czeka na drugie kliknięcie (pozycja)
  retypeOpen: null,      // pozycja dokumentu z otwartym wyborem nowego typu
};

const viewers = new WeakMap(); // File → podgląd PDF (renderowany raz)
let draftWritten = false;      // w tej sesji zapisano kopię roboczą bieżącej sprawy

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
  intake: $("intake"), result: $("result"),
  form: $("upload-form"), drop: $("drop"), input: $("file-input"), folderInput: $("folder-input"),
  list: $("file-list"), actions: $("actions"), submit: $("submit-btn"), note: $("actions-note"),
  cancel: $("cancel-btn"), announcer: $("announcer"),
  message: $("request-message"), messageText: $("request-text"), retryRequest: $("retry-request"),
  restoreBox: $("restore-box"), restoreText: $("restore-text"), restoreYes: $("restore-yes"), restoreNo: $("restore-no"),
  sheet: $("sheet"), work: document.querySelector(".work"),
  typesList: $("types-list"), typesSource: $("types-source"),
  // ekran 2: górny pasek (Pobierz ▾) i drugi pasek (Dokumenty ▾, ‹ › , Opcje ⋯)
  downloadSplit: $("download-split"), downloadZip: $("download-zip"), downloadMore: $("download-more"),
  downloadMenu: $("download-menu"), downloadZipItem: $("download-zip-item"), downloadZipNote: $("download-zip-note"),
  downloadJson: $("download-json"), downloadJsonNote: $("download-json-note"), unsavedNote: $("unsaved-note"),
  docsBtn: $("docs-btn"), docsBtnLabel: $("docs-btn-label"), docsPanel: $("docs-panel"), docList: $("doc-list"),
  retryFailed: $("retry-failed"), resubmit: $("resubmit-btn"), tally: $("tally"), cancelRetry: $("cancel-retry"),
  docPrev: $("doc-prev"), docNext: $("doc-next"), docPos: $("doc-pos"), docProgress: $("doc-progress"),
  docOptions: $("doc-options"), docOptionsMenu: $("doc-options-menu"),
  docRetry: $("doc-retry"), docRetryLabel: $("doc-retry-label"), docRetryNote: $("doc-retry-note"),
  docPdfToggle: $("doc-pdf-toggle"), docPdfLabel: $("doc-pdf-label"),
  docRetype: $("doc-retype"), docRevert: $("doc-revert"), docRevertNote: $("doc-revert-note"),
};

/* ---------- nawigacja ---------- */

const NAV_KEY = "o2j-nav";
const mobile = window.matchMedia("(max-width: 900px)");

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
  el.work.inert = open;   // przy otwartej szufladzie Tab nie ucieka do strony pod spodem
  if (open) el.rail.querySelector(".rail-item")?.focus();
}
// menu jest wysuwane na każdym ekranie, więc zmiana szerokości go nie zamyka

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
  if (false) {   // menu jest wysuwane na każdym ekranie, więc nie zajmuje miejsca
    el.app.dataset.nav = "collapsed";
    el.navToggle.setAttribute("aria-expanded", "false");
    el.navToggleLabel.textContent = "Rozwiń menu";
  }
}
el.menuBtn.addEventListener("click", () => setDrawer(true));
el.scrim.addEventListener("click", () => { setDrawer(false); el.menuBtn.focus(); });

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    setDrawer(false);
    if (state.view === "types") loadTypes();
    render();
    el.main.focus();
  });
});

$("new-case").addEventListener("click", () => {
  resetCase();
  state.view = "case";
  setDrawer(false);
  render();
  el.main.focus();
});

function resetCase() {
  state.abort?.abort();   // wynik przerwanej wysyłki nie trafi już do nowej sprawy
  state.urls.forEach((u) => URL.revokeObjectURL(u));
  Object.assign(state, {
    caseName: null, files: [], urls: [], results: null, meta: null,
    notice: null, lastRun: null, selected: null, pending: false, pendingSet: null, abort: null, slow: false,
    edits: [], active: null, saved: [], restore: null, confirmRerun: false, confirmDocRetry: null, retypeOpen: null,
  });
  draftWritten = false;
  el.input.value = "";
  el.folderInput.value = "";
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && el.app.dataset.drawer === "open") {
    setDrawer(false);
    el.menuBtn.focus();
    return;
  }
  // ↑/↓ przełączają dokument, gdy fokus jest na liście w panelu „Dokumenty”
  if ((event.key === "ArrowDown" || event.key === "ArrowUp") && event.target.closest?.(".doc-list")) {
    if (!state.files.length) return;
    event.preventDefault();
    const next = Math.min(state.files.length - 1, Math.max(0, (state.selected ?? 0) + (event.key === "ArrowDown" ? 1 : -1)));
    selectDocument(next);
    el.docList.querySelectorAll(".doc-main")[next]?.focus();
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
  const problem = skipped && !caseName
    ? `Pominięto ${skipped} ${skipped === 1 ? "plik, który nie jest" : "pliki, które nie są"} PDF-em.`
    : pdfs.length === 0 ? "W wybranym folderze nie ma plików PDF." : null;
  state.notice = problem ? { kind: "error", text: problem, retry: false } : null;
  if (state.selected === null && state.files.length) state.selected = 0;
  checkRestore();
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
// na ekranie wyniku pliki można upuścić na otwarty panel „Dokumenty” (zaczynają nową sprawę)
el.docsPanel.addEventListener("dragover", (event) => event.preventDefault());
el.docsPanel.addEventListener("drop", (event) => {
  event.preventDefault();
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
  checkRestore();
  render();
}

function selectDocument(index) {
  if (state.selected === index) return;
  state.confirmDocRetry = null;
  state.retypeOpen = null;
  state.selected = index;
  state.active = null;
  state.pdfFull = false;
  el.sheet.querySelectorAll(".pdfv-full").forEach((b) => b.setAttribute("aria-pressed", "false"));
  hideInsertButton();
  render();
}

/* ---------- wysyłka ---------- */

/* „Przetwórz ponownie” zastępuje wyniki i kasuje ręczne poprawki: przy poprawkach pyta drugim kliknięciem */
let rerunTimer = 0;
const editedFieldCount = () => (state.results ?? []).reduce((sum, r, i) => sum + (r?.status === "ok" ? countEdits(i) : 0), 0);
el.form.addEventListener("submit", (event) => {
  event.preventDefault();
  runExtraction(null);
});
el.resubmit.addEventListener("click", () => {
  if (state.pending) return;
  if (state.results && !state.confirmRerun && editedFieldCount() > 0) {
    state.confirmRerun = true;
    clearTimeout(rerunTimer);
    rerunTimer = setTimeout(() => { state.confirmRerun = false; render({ sheet: false }); }, 6000);
    render({ sheet: false });
    announce(el.resubmit.textContent);
    return;
  }
  clearTimeout(rerunTimer);
  state.confirmRerun = false;
  closePopovers();
  runExtraction(null);
});
el.retryFailed.addEventListener("click", () => { closePopovers({ focus: true }); runExtraction(failedPositions()); });
el.retryRequest.addEventListener("click", () => runExtraction(state.lastRun));
el.cancel.addEventListener("click", () => state.abort?.abort());
el.cancelRetry.addEventListener("click", () => state.abort?.abort());

el.restoreYes.addEventListener("click", restoreDraft);
el.restoreNo.addEventListener("click", dropDraft);

const failedPositions = () => (state.results ?? []).flatMap((r, i) => (r?.status === "error" ? [i] : []));

/** Fokus jest „wolny”, gdy nikt niczego nie edytuje: nie zabieramy go z rubryki ani z panelu. */
const focusIsFree = () => {
  const a = document.activeElement;
  return !a || a === document.body || a.hidden || !a.isConnected || !a.offsetParent
    || el.actions.contains(a) || a === el.cancelRetry;
};

/**
 * Wysyła pliki plik po pliku (każdy PDF osobnym POST /api/extract, najwyżej EXTRACT_CONCURRENCY naraz).
 * `positions` = null: cała sprawa (wyniki zastępowane), tablica pozycji: tylko te pliki, a ich wpisy
 * trafiają na swoje miejsca; reszta wyników i ręczne poprawki zostają. Każdy wynik jest pokazywany od razu,
 * błąd jednego pliku nie zatrzymuje pozostałych. Anulowanie przerywa trwające żądania i kolejkę;
 * gotowe wyniki zostają, a nieprzetworzone pliki dostają status błędu („Ponów błędne”).
 */
async function runExtraction(positions) {
  if (state.pending) return;
  if (state.files.length === 0) {
    state.notice = { kind: "error", text: "Wybierz co najmniej jeden plik PDF.", retry: false };
    render();
    return;
  }
  if (positions && (!state.results || positions.length === 0)) positions = null;
  const targets = positions ?? state.files.map((_, i) => i);
  const files = targets.map((i) => state.files[i]);
  const before = { results: state.results, meta: state.meta, edits: state.edits, saved: state.saved, selected: state.selected };
  const controller = new AbortController();
  const fileState = [];
  targets.forEach((i) => { fileState[i] = "queued"; });
  Object.assign(state, {
    pending: true, pendingSet: new Set(targets), abort: controller, fileState,
    slow: false, notice: null, active: null, restore: null,   // przetwarzanie od nowa zamiast przywracania
  });
  if (!positions) Object.assign(state, { results: null, meta: null });
  hideInsertButton();
  render();
  (positions ? el.cancelRetry : el.cancel).focus();   // przycisk, którym zaczęto, jest teraz zablokowany

  const extractOne = state.mode === "mock"
    ? (file, opts) => extractWithMock([file], { ...opts, delayMs: 650 + Math.round(Math.random() * 500) })
    : (file, opts) => extractWithApi([file], opts);
  const started = performance.now();
  const slowTimer = setTimeout(() => {
    if (state.abort !== controller) return;
    state.slow = true;
    render({ sheet: false });   // bez przebudowy arkusza: nie zabieramy fokusu z rubryki
  }, 8000);
  let first = !positions;   // pierwszy wynik całej sprawy otwiera ekran wyniku
  let meta = null;

  const outcome = await extractEach(files, {
    extractOne,
    signal: controller.signal,
    onStart: (k) => {
      if (state.abort !== controller) return;
      state.fileState[targets[k]] = "running";
      render({ sheet: false });
    },
    onResult: (k, entry, m) => {
      if (state.abort !== controller) return;
      const pos = targets[k];
      meta ??= m;
      const free = focusIsFree();
      delete state.fileState[pos];
      if (first) {
        // pierwszy gotowy dokument: ekran wyniku, wcześniejsze poprawki przepadają (jak dotąd przy „Przetwórz ponownie”)
        first = false;
        Object.assign(state, { results: state.files.map(() => null), edits: [], saved: [], selected: pos });
      }
      state.results[pos] = entry;
      delete state.edits[pos];
      delete state.saved[pos];
      // arkusz przebudowujemy tylko dla dokumentu, który właśnie się otworzył albo jest wybrany
      render({ sheet: pos === state.selected });
      if (free && !el.result.hidden && (!document.activeElement || document.activeElement === document.body || !document.activeElement.offsetParent)) el.docsBtn.focus();
      const sum = docsSummary(state.files.map((_, i) => statusAt(i)));
      announce(`${entry.filename}: ${entry.status === "ok" ? typeLabel(entry.type) : STATUS[entry.status]?.text ?? entry.status}. ${sum.progress ?? ""}`);
    },
  });
  clearTimeout(slowTimer);
  if (state.abort !== controller) return;   // w międzyczasie zaczęto nową sprawę

  const free = focusIsFree();
  const seconds = (performance.now() - started) / 1000;
  Object.assign(state, { pending: false, pendingSet: null, abort: null, slow: false, fileState: [] });

  if (outcome.aborted && !state.results) {
    // nic jeszcze nie przyszło: wracamy do stanu sprzed wysyłki
    Object.assign(state, before);
    state.notice = {
      kind: "info", retry: false,
      text: state.results
        ? "Przetwarzanie anulowane. Wcześniejsze wyniki i poprawki zostały bez zmian."
        : "Przetwarzanie anulowane. Pliki zostały na liście, możesz je przetworzyć ponownie.",
    };
  } else {
    let missing = 0;
    targets.forEach((pos, k) => {
      if (outcome.documents[k]) return;
      // przerwane przed wynikiem: przy ponawianiu zostaje poprzedni wpis, przy całej sprawie plik ma błąd do ponowienia
      if (positions && before.results?.[pos]) { state.results[pos] = before.results[pos]; return; }
      missing += 1;
      state.results[pos] = {
        filename: state.files[pos].name, status: "error", type: null, data: null,
        error: { code: "cancelled", message: "Przetwarzanie przerwane przed wynikiem." },
      };
    });
    state.meta = positions ? { ...state.meta, ...(meta ?? {}), seconds } : { ...(meta ?? {}), seconds };
    state.lastRun = null;
    const done = outcome.documents.filter(Boolean);
    if (outcome.aborted) {
      state.notice = {
        kind: "info", retry: false,
        text: `Przetwarzanie anulowane: gotowe ${done.length} z ${targets.length}. ${missing ? "Pozostałe pliki przetworzysz przyciskiem „Ponów błędne” w panelu „Dokumenty”." : "Wcześniejsze wyniki zostały bez zmian."}`,
      };
    } else if (done.length && done.every((d) => d.error?.code === "network_error")) {
      state.notice = { kind: "error", retry: false, text: "Brak połączenia z serwerem. Sprawdź, czy backend działa, i użyj „Ponów błędne” w panelu „Dokumenty”." };
    }
    announce(`${positions ? "Ponowiono" : "Przetworzono"} ${done.length} ${plural(done.length, "plik", "pliki", "plików")}. ${tallyText(done)}`);
  }
  // arkusz wybranego dokumentu był już zbudowany, gdy przyszedł jego wynik: przebudowa zabrałaby fokus z rubryki
  const sheetStale = !state.results || state.selected === null
    || targets.some((pos, k) => pos === state.selected && !outcome.documents[k]);
  render({ sheet: sheetStale });
  scheduleDraftSave();
  if (free) ((state.results ? el.docsBtn : el.submit)).focus();
}

function tallyText(documents) {
  const count = (s) => documents.filter((d) => d.status === s).length;
  return [["rozpoznane", count("ok")], ["nierozpoznane", count("unknown")], ["z błędem", count("error")]]
    .filter(([, n]) => n).map(([label, n]) => `${label}: ${n}`).join(", ")
    .replace(/^./, (c) => c.toUpperCase()) + ".";
}

/** Komunikat tylko dla czytnika ekranu (region role="status"). */
function announce(text) {
  el.announcer.textContent = "";
  setTimeout(() => { el.announcer.textContent = text; }, 50);
}

/* ---------- render ---------- */

function statusAt(index) {
  const run = state.pending ? state.fileState?.[index] : null;
  if (run === "queued") return "queued";
  if (run === "running") return "pending";
  return state.results?.[index]?.status ?? "selected";
}

/** Ekran 1 (wgrywanie i przetwarzanie całości) albo ekran 2 (wynik sprawy). */
const screenNow = () => (state.results ? "result" : "intake");

function render({ sheet = true } = {}) {
  el.viewCase.hidden = state.view !== "case";
  el.viewHelp.hidden = state.view !== "help";
  el.viewTypes.hidden = state.view !== "types";
  el.app.dataset.view = state.view;
  document.querySelectorAll(".rail-item[data-view]").forEach((b) => {
    if (b.dataset.view === state.view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  const screen = screenNow();
  el.viewCase.dataset.screen = screen;
  el.intake.hidden = screen !== "intake";
  el.result.hidden = screen !== "result";
  if (screen !== "result") closePopovers();
  el.modeFlag.hidden = state.mode !== "mock";
  el.title.textContent = state.view === "help" ? "Instrukcja"
    : state.view === "types" ? "Typy dokumentów"
    : state.caseName ? `Sprawa: ${state.caseName}` : "Sprawa odwoławcza";
  // kroki tylko na ekranie wgrywania i w trakcie przetwarzania; pobieranie tylko na ekranie wyniku
  el.steps.hidden = state.view !== "case" || screen !== "intake";
  el.downloadSplit.hidden = state.view !== "case" || screen !== "result";

  const step = state.pending ? 2 : state.files.length ? 2 : 1;
  el.steps.querySelectorAll("li").forEach((li) => {
    const n = Number(li.dataset.step);
    li.dataset.state = n < step ? "done" : n === step ? "current" : "todo";
    if (n === step) li.setAttribute("aria-current", "step");
    else li.removeAttribute("aria-current");
  });

  el.input.disabled = state.pending;
  el.folderInput.disabled = state.pending;
  el.drop.dataset.compact = String(state.files.length > 0);
  el.drop.dataset.busy = String(state.pending);
  const notice = state.notice;
  el.message.hidden = !notice;
  el.message.dataset.kind = notice?.kind ?? "error";
  el.messageText.textContent = notice?.text ?? "";
  el.retryRequest.hidden = !notice?.retry || state.pending;
  el.restoreBox.hidden = !state.restore;
  if (state.restore) el.restoreText.textContent = `W tej przeglądarce jest kopia robocza tej sprawy: ${describeDraft(state.restore.draft)}. Przywrócenie wczyta zapisane wyniki i poprawki bez ponownego przetwarzania.`;
  el.actions.hidden = state.files.length === 0;
  el.submit.disabled = state.pending;
  el.submit.classList.toggle("btn-line", Boolean(state.restore));   // przy pytaniu o kopię główną akcją jest „Przywróć”
  const n = state.files.length;
  el.submit.textContent = state.pending ? "Przetwarzanie…" : `Przetwórz ${n} ${plural(n, "plik", "pliki", "plików")}`;
  el.cancel.hidden = !(state.pending && screen === "intake");
  el.cancelRetry.hidden = !(state.pending && screen === "result");
  const progress = state.pending ? docsSummary(state.files.map((_, i) => statusAt(i))).progress : "";
  el.note.textContent = !state.pending ? ""
    : state.slow ? `${progress}. To trwa dłużej niż zwykle. Model wciąż czyta dokumenty. Możesz poczekać albo anulować.`
    : `${progress}. Każdy plik jest wysyłany osobno; wynik pojawi się od razu, gdy będzie gotowy.`;

  // panel „Dokumenty”: ponawianie i przetwarzanie od nowa
  const failed = state.pending ? 0 : failedPositions().length;
  el.retryFailed.hidden = failed === 0;
  el.retryFailed.textContent = `Ponów błędne (${failed})`;
  el.resubmit.disabled = state.pending;
  el.resubmit.textContent = state.results && state.confirmRerun
    ? `Kliknij jeszcze raz: usunie poprawki (${editedFieldCount()})`
    : "Przetwórz ponownie";
  el.resubmit.dataset.confirm = String(Boolean(state.confirmRerun));

  renderList();
  renderDocbar();
  renderSummary();
  if (sheet) renderSheet();
}

/** Ikona statusu + tekst (kolor tylko w ikonie, status nigdy samym kolorem). */
function statusNode(status, entry, className = "badge") {
  const info = STATUS[status] ?? STATUS.selected;
  const span = node("span", `${className} badge-${status}`);
  span.innerHTML = `<svg class="ic" aria-hidden="true"><use href="#i-${info.icon}"/></svg>`;
  span.append(status === "ok" ? typeLabel(entry.type) : info.text);
  return span;
}
const badgeFor = (status, entry) => statusNode(status, entry);

function renderList() {
  el.list.replaceChildren(...state.files.map(renderFileRow));
  el.docList.replaceChildren(...(state.results ? state.files.map(renderDocRow) : []));
}

/** Ekran 1: nr, nazwa, rozmiar, × (w trakcie przetwarzania zamiast × status). */
function renderFileRow(file, index) {
  const status = statusAt(index);
  const li = node("li", "file-row");
  const pos = node("span", "file-pos", String(index + 1));
  pos.setAttribute("aria-hidden", "true");
  const main = node("div", "file-main");
  main.append(node("span", "sr-only", `Pozycja ${index + 1}: `), fileNameNode("span", "file-name", file.name));
  const meta = node("span", "file-meta", formatSize(file.size));
  li.append(pos, main, meta);
  if (status === "pending" || status === "queued") {
    li.append(statusNode(status, null, "badge file-state"));
  } else if (!state.pending) {
    const remove = node("button", "file-remove");
    remove.type = "button";
    remove.setAttribute("aria-label", `Usuń ${file.name} z listy`);
    remove.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-close"/></svg>';
    remove.addEventListener("click", () => removeFile(index));
    li.append(remove);
  }
  return li;
}

/** Ekran 2, panel „Dokumenty”: wybór dokumentu, status, wypełnienie, poprawki. */
function renderDocRow(file, index) {
  const status = statusAt(index);
  const entry = state.results?.[index];
  const li = node("li", "doc-row");
  li.dataset.current = String(index === state.selected);
  const b = node("button", "doc-main");
  b.type = "button";
  b.setAttribute("aria-current", String(index === state.selected));
  const pos = node("span", "doc-pos", String(index + 1));
  pos.setAttribute("aria-hidden", "true");
  const text = node("span", "doc-text");
  const meta = node("span", "doc-meta");
  meta.append(statusNode(status, entry));
  if (entry?.status === "ok") {
    const c = completeness(entry, dataAt(index));
    if (c) meta.append(node("span", null, `${c.filled}/${c.total} pól`));
    const edits = countEdits(index);
    if (entry.manualType) meta.append(node("span", "doc-edited", "typ ręcznie"));
    if (edits) meta.append(node("span", "doc-edited", `${edits} ${plural(edits, "poprawka", "poprawki", "poprawek")}`));
  }
  text.append(node("span", "sr-only", `Pozycja ${index + 1}: `), fileNameNode("span", "doc-name", file.name), meta);
  b.append(pos, text);
  b.addEventListener("click", () => {
    selectDocument(index);
    closePopovers({ focus: true });
  });
  li.append(b);
  return li;
}

/* ---------- drugi pasek: Dokumenty ▾, ‹ nazwa · 1 z 5 ›, wypełnienie, ⋯ ---------- */

function renderDocbar() {
  if (!state.results) return;
  const statuses = state.files.map((_, i) => statusAt(i));
  const sum = docsSummary(statuses);
  el.docsBtnLabel.replaceChildren(`Dokumenty ${sum.count}`);
  if (sum.attention) {
    // informacja o błędach widoczna także przy zamkniętym panelu: tekst, ikona tylko jako dodatek
    const att = node("span", `docbar-attention${sum.alert ? " is-alert" : ""}`);
    att.append(node("span", "docbar-sep", "·"));
    if (sum.alert) att.insertAdjacentHTML("beforeend", '<svg class="ic ic-sm" aria-hidden="true"><use href="#i-error"/></svg>');
    att.append(sum.attention);
    el.docsBtnLabel.append(att);
  }
  const index = state.selected ?? 0;
  const file = state.files[index];
  const entry = state.results[index];
  el.docPos.textContent = file ? positionText(file.name, index, state.files.length) : "";
  el.docPrev.disabled = index <= 0;
  el.docNext.disabled = index >= state.files.length - 1;
  const c = entry?.status === "ok" ? completeness(entry, dataAt(index)) : null;
  el.docProgress.textContent = entry?.status === "ok" ? progressText(c, countEdits(index)) : "";
  // ⋯ Opcje dokumentu
  const edits = entry?.status === "ok" ? countEdits(index) : 0;
  el.docRetry.disabled = state.pending;
  el.docRetryLabel.textContent = state.confirmDocRetry === index
    ? `Kliknij jeszcze raz: usunie poprawki (${edits})`
    : "Przetwórz ten plik ponownie";
  el.docRetryNote.textContent = edits && state.confirmDocRetry !== index ? "poprawki w tym pliku przepadną" : "";
  el.docPdfLabel.textContent = state.showPdf ? "Ukryj podgląd PDF" : "Pokaż podgląd PDF";
  el.docRetype.hidden = entry?.status !== "ok";
  el.docRetype.disabled = state.pending;
  el.docRevert.hidden = !entry?.manualType;
  el.docRevertNote.textContent = entry?.previous
    ? (entry.previous.status === "ok" ? `typ od modelu: ${typeLabel(entry.previous.type)}` : "model nie rozpoznał typu")
    : "";
}

el.docPrev.addEventListener("click", () => selectDocument(Math.max(0, (state.selected ?? 0) - 1)));
el.docNext.addEventListener("click", () => selectDocument(Math.min(state.files.length - 1, (state.selected ?? 0) + 1)));

let docRetryTimer = 0;
el.docRetry.addEventListener("click", () => {
  const index = state.selected;
  if (index === null || state.pending) return;
  const edits = state.results?.[index]?.status === "ok" ? countEdits(index) : 0;
  if (edits && state.confirmDocRetry !== index) {
    state.confirmDocRetry = index;
    clearTimeout(docRetryTimer);
    docRetryTimer = setTimeout(() => { state.confirmDocRetry = null; renderDocbar(); }, 6000);
    renderDocbar();
    announce(el.docRetryLabel.textContent);
    return;
  }
  state.confirmDocRetry = null;
  closePopovers({ focus: true });
  runExtraction([index]);
});
el.docRetype.addEventListener("click", () => {
  state.retypeOpen = state.selected;
  closePopovers();
  renderSheet();
  el.sheet.querySelector(".retype select")?.focus();
});
el.docRevert.addEventListener("click", () => {
  closePopovers({ focus: true });
  revertManualType(state.selected);
});
el.docPdfToggle.addEventListener("click", () => {
  state.showPdf = !state.showPdf;
  try { localStorage.setItem("o2j-pdf", state.showPdf ? "1" : "0"); } catch { /* bez pamięci */ }
  closePopovers({ focus: true });
  renderDocbar();
  renderSheet();
});

/* ---------- panele rozwijane pod przyciskiem (Dokumenty, Pobierz, Opcje) ----------
   Esc i kliknięcie obok zamykają panel, fokus wraca do przycisku. */

const POPOVERS = [];
function popover(trigger, panel, { onOpen } = {}) {
  const p = { trigger, panel };
  p.open = () => {
    closePopovers();
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    onOpen?.();
  };
  p.close = (focus = false) => {
    if (panel.hidden) return;
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (focus) trigger.focus();
  };
  trigger.addEventListener("click", () => (panel.hidden ? p.open() : p.close()));
  POPOVERS.push(p);
  return p;
}
function closePopovers({ focus = false } = {}) {
  POPOVERS.forEach((p) => p.close(focus && !p.panel.hidden));
}
const openPopover = () => POPOVERS.find((p) => !p.panel.hidden);

popover(el.docsBtn, el.docsPanel, {
  onOpen: () => (el.docList.querySelector('[aria-current="true"]') ?? el.docList.querySelector("button"))?.focus(),
});
popover(el.downloadMore, el.downloadMenu, { onOpen: () => el.downloadZipItem.focus() });
popover(el.docOptions, el.docOptionsMenu, { onOpen: () => el.docRetry.focus() });

document.addEventListener("pointerdown", (event) => {
  const p = openPopover();
  if (p && !p.panel.contains(event.target) && !p.trigger.contains(event.target)) p.close();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const p = openPopover();
  if (!p) return;
  event.stopImmediatePropagation();
  p.close(true);
}, true);

/* ---------- podsumowanie sprawy i pobieranie ---------- */

function renderSummary() {
  if (!state.results) {
    el.tally.replaceChildren();
    el.unsavedNote.hidden = true;
    return;
  }
  const byType = new Map();
  for (const r of state.results) if (r?.status === "ok") byType.set(r.type, (byType.get(r.type) ?? 0) + 1);
  const order = [...Object.keys(DOC_TYPES), ...[...byType.keys()].filter((t) => !DOC_TYPES[t])];
  const rows = order.map((type) => [typeLabel(type), byType.get(type) ?? 0, !byType.get(type)]);
  const unknown = state.results.filter((r) => r?.status === "unknown").length;
  const errors = state.results.filter((r) => r?.status === "error").length;
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
    if (Number.isFinite(state.meta.seconds)) info.push(`${state.meta.seconds.toFixed(1).replace(".", ",")} s`);
    if (state.meta.restored) info.push("przywrócono z kopii");
    const div = node("div", "tally-meta");
    div.append(node("dt", null, "Przebieg"), node("dd", null, info.join(" · ")));
    items.push(div);
  }
  el.tally.replaceChildren(...items);

  const files = resultFiles();
  const zipText = `${files.length} ${plural(files.length, "plik", "pliki", "plików")} JSON`;
  el.downloadZip.disabled = files.length === 0 || state.pending;
  el.downloadZipItem.disabled = el.downloadZip.disabled;
  const waiting = state.pending ? state.files.filter((_, i) => ["queued", "pending"].includes(statusAt(i))).length : 0;
  el.downloadZipNote.textContent = waiting
    ? `ZIP po zakończeniu: czeka jeszcze ${waiting} ${plural(waiting, "plik", "pliki", "plików")}`
    : files.length ? `${safeName(state.caseName ?? "sprawa")}.zip · ${zipText}` : "brak plików do pobrania";
  el.downloadZip.title = waiting ? el.downloadZipNote.textContent
    : `Pobierz ZIP całej sprawy (${zipText})${unsaved().length ? ". Są niepobrane poprawki." : ""}`;
  const index = state.selected;
  const entry = index !== null ? state.results[index] : null;
  el.downloadJson.disabled = entry?.status !== "ok";
  el.downloadJsonNote.textContent = entry?.status === "ok" ? jsonName(state.files[index].name)
    : entry?.status === "unknown" ? "nierozpoznany: w ZIP-ie jako {}" : "ten plik nie ma danych";
  const open = unsaved().length;
  el.downloadSplit.dataset.unsaved = String(open > 0);
  el.unsavedNote.hidden = !open;
  el.unsavedNote.textContent = open
    ? `Poprawki w ${open} ${plural(open, "dokumencie", "dokumentach", "dokumentach")} nie są jeszcze pobrane. Kopia robocza zostaje w tej przeglądarce.`
    : "";
}

/** Pliki wynikowe jak w output/<sprawa>/ (export.js): JSON dla rozpoznanych, `{}` dla nierozpoznanych. */
function resultFiles() {
  return buildResultFiles({ files: state.files, results: state.results, dataAt, caseName: state.caseName });
}

function downloadZip() {
  const files = resultFiles();
  if (!files.length) return;
  downloadBlob(`${safeName(state.caseName ?? "sprawa")}.zip`, zipStore(files));
  markSaved(state.results.map((_, i) => i));
}
el.downloadZip.addEventListener("click", downloadZip);
el.downloadZipItem.addEventListener("click", () => { closePopovers({ focus: true }); downloadZip(); });
el.downloadJson.addEventListener("click", () => {
  const index = state.selected;
  if (index === null || state.results?.[index]?.status !== "ok") return;
  closePopovers({ focus: true });
  downloadJson(state.files[index].name, dataAt(index));
  markSaved([index]);
});

/* ---------- arkusz: formularz | PDF ---------- */

function renderSheet() {
  const index = state.selected;
  const file = index !== null ? state.files[index] : null;
  if (!file || !state.results) {
    el.sheet.replaceChildren();
    return;
  }

  const entry = state.results[index];
  const status = statusAt(index);
  const head = node("div", "col-head");
  const title = node("h2", "col-title");
  title.id = "sheet-heading";
  title.append(node("span", "sr-only", `${file.name}: `));

  let left;
  if (status === "pending" || status === "queued" || !entry) {
    title.append(statusNode(status === "queued" ? "queued" : "pending", entry, "col-status"));
    left = node("div", "skeleton");
    for (let i = 0; i < 8; i++) left.append(node("div"));
    left.append(node("p", "sr-only", "Trwa przetwarzanie dokumentu."));
    head.append(title);
  } else if (entry.status === "unknown") {
    title.append(statusNode("unknown", entry, "col-status"));
    head.append(title);
    left = stateBlock("Nie rozpoznano typu dokumentu", [
      "Model nie rozpoznał typu. Jeśli to jeden z obsługiwanych dokumentów, wybierz typ:",
    ]);
    left.append(typePicker(index, null), node("p", "state-note",
      "Bez wyboru typu plik trafi do wyników sprawy jako JSON z samym {}, zgodnie z wymogiem UZP."));
  } else if (entry.status === "error") {
    title.append(statusNode("error", entry, "col-status"));
    head.append(title);
    // skanu bez OCR nie naprawi ponowienie, więc nie obiecujemy tego
    const ocr = entry.error?.code === "ocr_required";
    left = stateBlock("Nie udało się przetworzyć pliku", [
      entry.error?.message ?? "Wystąpił błąd podczas odczytu dokumentu.",
      ocr
        ? "To skan bez warstwy tekstu, a serwer nie odczytał go przez OCR. Pozostałe pliki sprawy są dostępne; dane z tego pisma trzeba wprowadzić ręcznie albo wgrać PDF z tekstem."
        : "Pozostałe pliki sprawy są dostępne. Ten plik nie trafi do wyników, dopóki nie uda się go przetworzyć: użyj „Ponów błędne” w panelu „Dokumenty”.",
    ]);
    if (entry.error?.code) left.append(node("p", "state-code", `Kod błędu: ${entry.error.code}`));
  } else {
    title.append(typeLabel(entry.type));
    if (entry.manualType) title.append(node("span", "col-manual", "typ ustawiony ręcznie"));
    head.append(title, sheetModeSwitch());
    left = state.sheetMode === "json" ? jsonView(dataAt(index)) : fieldsView(index, entry);
    if (state.sheetMode === "fields") {
      head.append(node("p", "col-hint", state.showPdf
        ? "Wpisuj wprost w rubryki albo zaznacz tekst w PDF-ie i wstaw go do rubryki (z klawiatury: Alt+↓ w rubryce)."
        : "Wpisuj wprost w rubryki."));
    }
  }

  const body = node("div", "sheet-body");
  const pane = node("div", "fields-pane");
  pane.append(head);
  if (state.retypeOpen === index && entry?.status === "ok") pane.append(retypePanel(index, entry));
  pane.append(left);
  body.dataset.pdf = String(state.showPdf);
  body.dataset.full = String(state.showPdf && state.pdfFull);
  body.style.setProperty("--split", `${state.split}%`);
  if (state.showPdf) body.append(pane, splitter(body), pdfPane(index));
  else body.append(pane);
  el.sheet.replaceChildren(body);
}

/* ---------- ręczna zmiana typu dokumentu ---------- */

/** Typy, które da się ustawić ręcznie: znane panelowi (fields.js). */
function manualTypes() {
  return Object.entries(DOC_TYPES).map(([id, t]) => ({ id, label: t.label }));
}

/** Lista typów i przycisk. `current` = typ, którego nie proponujemy (bieżący). */
function typePicker(index, current, { confirmText = "Otwórz formularz", onCancel = null } = {}) {
  const wrap = node("div", "type-pick");
  const id = `type-pick-${index}`;
  const label = node("label", "type-pick-label", "Typ dokumentu");
  label.htmlFor = id;
  const select = node("select", "wiz-in type-pick-select");
  select.id = id;
  select.append(Object.assign(node("option", null, "— wybierz —"), { value: "" }));
  for (const t of manualTypes().filter((t) => t.id !== current)) select.append(Object.assign(node("option", null, t.label), { value: t.id }));
  const go = node("button", "btn btn-line btn-sm", confirmText);
  go.type = "button";
  go.disabled = true;
  select.addEventListener("change", () => { go.disabled = !select.value; });
  go.addEventListener("click", () => select.value && setManualType(index, select.value));
  const row = node("div", "type-pick-row");
  row.append(select, go);
  if (onCancel) {
    const cancel = node("button", "link-btn", "Anuluj");
    cancel.type = "button";
    cancel.addEventListener("click", onCancel);
    row.append(cancel);
  }
  wrap.append(label, row);
  return wrap;
}

/** Potwierdzenie zmiany typu rozpoznanego dokumentu: pola bieżącego typu przepadną. */
function retypePanel(index, entry) {
  const box = node("section", "retype");
  box.setAttribute("aria-label", "Zmiana typu dokumentu");
  const edits = countEdits(index);
  box.append(node("p", "retype-text",
    `Zmiana typu usunie pola typu „${typeLabel(entry.type)}”${edits ? ` i ${edits} ${plural(edits, "poprawkę", "poprawki", "poprawek")}` : ""}. Otworzy się pusty formularz nowego typu do ręcznego wypełnienia.`));
  box.append(typePicker(index, entry.type, {
    confirmText: "Zmień typ",
    onCancel: () => { state.retypeOpen = null; renderSheet(); el.docOptions.focus(); },
  }));
  return box;
}

function setManualType(index, type) {
  state.results[index] = retypeEntry(state.results[index], type);
  delete state.edits[index];
  delete state.saved[index];
  Object.assign(state, { retypeOpen: null, sheetMode: "fields", active: null });
  render();
  scheduleDraftSave();
  announce(`Ustawiono typ: ${typeLabel(type)}. Formularz jest pusty, uzupełnij go ręcznie.`);
  el.sheet.querySelector(".fields-pane input, .fields-pane textarea")?.focus();
}

/** Źródło pola: otwiera podgląd (gdy schowany), przechodzi do strony i podświetla fragment. */
function showSource(index, page, text) {
  if (!state.showPdf || state.pdfFull) {
    state.showPdf = true;
    try { localStorage.setItem("o2j-pdf", "1"); } catch { /* bez pamięci */ }
    renderDocbar();
    renderSheet();
  }
  const viewer = viewers.get(state.files[index]);
  viewer?.element.showSource?.(page, text == null ? null : String(text));
  announce(`Podgląd PDF: strona ${page}.`);
}

/** Powrót do rozpoznania modelu (wpis sprzed ręcznej zmiany typu). */
function revertManualType(index) {
  const previous = state.results[index]?.previous;
  if (!previous) return;
  state.results[index] = previous;
  delete state.edits[index];
  delete state.saved[index];
  state.retypeOpen = null;
  render();
  scheduleDraftSave();
  announce("Przywrócono rozpoznanie modelu.");
}

/** „Formularz / JSON” w nagłówku kolumny formularza. */
function sheetModeSwitch() {
  const seg = node("div", "seg");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", "Widok danych");
  for (const [mode, label] of [["fields", "Formularz"], ["json", "JSON"]]) {
    const b = node("button", null, label);
    b.type = "button";
    b.setAttribute("aria-pressed", String(state.sheetMode === mode));
    b.addEventListener("click", () => { state.sheetMode = mode; state.active = null; hideInsertButton(); renderSheet(); });
    seg.append(b);
  }
  return seg;
}

/** Po wpisaniu wartości: odświeża liczniki bez przebudowy arkusza (fokus zostaje). */
function refreshAfterEdit(index) {
  renderList();
  renderDocbar();
  renderSummary();
  scheduleDraftSave();
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
  viewer.element.dataset.target = state.active?.index === index ? state.active.field.label : "";
  wrap.append(viewer.element);
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
  return countChanges(state.edits[index], state.results?.[index]?.data);
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
    map.set(ev.field_path, {
      label: [ev.page_number && `str. ${ev.page_number}`, ev.method].filter(Boolean).join(" · "),
      page: ev.page_number ?? null,
      text: ev.text ?? null,
    });
  }
  return map;
}

/* ---------- kopia robocza poprawek (draft.js) ----------
   Po każdej poprawce dane sprawy trafiają do localStorage. Po ponownym wczytaniu
   tych samych plików (nazwy i rozmiary) panel pyta „Przywrócić poprawki?”.
   Przy próbie zamknięcia lub odświeżenia strony z niepobranymi poprawkami
   przeglądarka pokazuje ostrzeżenie. */

function readStore() {
  try { return parseStore(localStorage.getItem(DRAFT_STORAGE_KEY)); } catch { return parseStore(null); }
}
function writeStore(store) {
  try {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(store));
    return true;
  } catch {
    return false;   // tryb prywatny, zablokowana pamięć albo brak miejsca: panel działa dalej bez kopii
  }
}

let draftTimer = 0;
function scheduleDraftSave() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(saveDraftNow, 400);
}
function saveDraftNow() {
  clearTimeout(draftTimer);
  if (!state.results || state.pending || state.restore) return;
  const key = caseKey(state.files);
  const draft = buildDraft({
    files: state.files, results: state.results, edits: state.edits, meta: state.meta, caseName: state.caseName,
  });
  // bez poprawek kasujemy tylko kopię zapisaną w tej sesji (np. po cofnięciu wszystkich zmian);
  // starszej kopii nie ruszamy, dopóki użytkownik sam jej nie odrzuci albo nie nadpisze nową poprawką
  if (!draft && !draftWritten) return;
  if (writeStore(putDraft(readStore(), key, draft))) draftWritten = Boolean(draft);
}

/** Po zmianie listy plików: czy w pamięci jest kopia dokładnie tej sprawy? */
function checkRestore() {
  const draft = !state.results && state.files.length ? findDraft(readStore(), state.files) : null;
  const was = state.restore;
  state.restore = draft ? { draft } : null;
  if (draft && !was) announce(`Przywrócić poprawki? ${describeDraft(draft)}.`);
}

function restoreDraft() {
  const draft = state.restore?.draft;
  const aligned = draft && alignDraft(draft, state.files);
  state.restore = null;
  if (!aligned) {
    state.notice = { kind: "error", text: "Nie udało się przywrócić poprawek: zestaw plików się zmienił.", retry: false };
    render();
    return;
  }
  // pokazujemy pierwszy poprawiony dokument, żeby od razu było widać, co wróciło
  const firstEdited = aligned.edits.findIndex(Boolean);
  const firstOk = aligned.results.findIndex((r) => r?.status === "ok");
  Object.assign(state, {
    results: aligned.results, edits: aligned.edits, saved: [],
    meta: draft.meta ? { ...draft.meta, restored: true } : null,
    selected: firstEdited >= 0 ? firstEdited : Math.max(0, firstOk), notice: null, active: null,
  });
  if (!state.caseName && draft.caseName) state.caseName = draft.caseName;
  draftWritten = true;
  render();
  announce(`Przywrócono poprawki: ${describeDraft(draft)}.`);
  el.docsBtn.focus();
}

function dropDraft() {
  if (state.restore) writeStore(putDraft(readStore(), state.restore.draft.key, null));
  state.restore = null;
  render();
  el.submit.focus();
}

function markSaved(positions) {
  positions.forEach((i) => { state.saved[i] = JSON.stringify(dataAt(i)); });
  renderSummary();
}

const unsaved = () => unsavedPositions({ results: state.results, edits: state.edits, saved: state.saved });   // także ręczna zmiana typu

window.addEventListener("beforeunload", (event) => {
  saveDraftNow();
  if (!unsaved().length && !state.pending) return;
  event.preventDefault();
  event.returnValue = "";   // starsze przeglądarki pokazują okno tylko z ustawionym returnValue
});
window.addEventListener("pagehide", saveDraftNow);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") saveDraftNow(); });

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
      wrap.append(...listGroup(group, value, ctx));
    } else {
      wrap.append(groupBlock(group.title, group.fields.map((f) =>
        fieldBlock(f, getPath(value, f.key), ctx, `${group.path}.${f.key}`))));
    }
  }
  return wrap;
}

/**
 * Grupa z listą pozycji (np. kilku pełnomocników): „Usuń” przy tytule pozycji, gdy jest ich więcej
 * niż jedna, i cichy „+ Dodaj …” pod ostatnią. Zmiana listy to poprawka jak każda inna
 * (licznik, „poprawione · cofnij”, kopia robocza, eksport).
 */
function listGroup(group, value, ctx) {
  const index = ctx.index;
  const listPath = group.path;
  // pusta lista: pokazujemy puste rubryki pierwszej pozycji, żeby dało się je uzupełnić
  const items = Array.isArray(value) && value.length ? value : [{}];
  const original = getPath(state.results[index].data, listPath);
  const countChanged = (Array.isArray(original) ? original.length : 0) !== (Array.isArray(value) ? value.length : 0);
  const noun = group.item ?? "pozycję";
  const blocks = items.map((item, i) => {
    const title = items.length > 1 ? `${group.title} ${i + 1}` : group.title;
    const extra = [];
    if (i === 0 && countChanged) {
      const undo = node("button", "link-btn", "cofnij");
      undo.type = "button";
      undo.setAttribute("aria-label", `Cofnij zmiany listy: ${group.title}`);
      undo.addEventListener("click", () => {
        setValue(index, listPath, structuredClone(original ?? []));
        renderSheet();
        refreshAfterEdit(index);
        announce(`Przywrócono listę: ${group.title}.`);
      });
      extra.push(node("span", null, "lista poprawiona"), undo);
    }
    if (items.length > 1) {
      const remove = node("button", "link-btn", "Usuń");
      remove.type = "button";
      remove.setAttribute("aria-label", `Usuń pozycję: ${title}`);
      remove.addEventListener("click", () => {
        const next = structuredClone(items);
        next.splice(i, 1);
        setValue(index, listPath, next);
        renderSheet();
        refreshAfterEdit(index);
        announce(`Usunięto: ${title}. Zmianę można cofnąć.`);
        el.sheet.querySelectorAll(".group-add")[0]?.focus();
      });
      extra.push(remove);
    }
    return groupBlock(title, group.fields.map((f) =>
      fieldBlock(f, getPath(item, f.key), ctx, `${listPath}.${i}.${f.key}`)), extra);
  });
  const add = node("button", "link-btn group-add", `+ Dodaj ${noun}`);
  add.type = "button";
  add.addEventListener("click", () => {
    const current = Array.isArray(value) ? structuredClone(value) : [];
    current.push(emptyListItem(group.fields, current[0] ?? original?.[0] ?? null));
    setValue(index, listPath, current);
    renderSheet();
    refreshAfterEdit(index);
    announce(`Dodano pustą pozycję: ${group.title} ${current.length}.`);
    // fokus na pierwszą rubrykę nowej pozycji
    const prefix = `f-${index}-${listPath.replace(/[^\w]/g, "_")}_${current.length - 1}_`;
    el.sheet.querySelector(`input[id^="${prefix}"], textarea[id^="${prefix}"]`)?.focus();
  });
  blocks.at(-1).append(add);
  return blocks;
}

function groupBlock(title, children, extra = []) {
  const section = node("section", "group");
  const head = node("h3", "group-title", title);
  if (extra.length) {
    const tags = node("span", "group-tags");
    tags.append(...extra);
    head.append(tags);
  }
  section.append(head);
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
  // wybór tak/nie: etykieta nazywa grupę, ale kliknięcie w nią nie może zaznaczać „tak”
  const choice = field.kind === "bool" || field.kind === "enum";
  const head = node("div", "field-label");
  const label = node(choice ? "span" : "label", "field-name");
  if (choice) label.id = `${id}-label`;
  else label.htmlFor = id;
  label.append(node("span", "field-no", `${ctx.n}.`), " ", field.label);
  if (field.hint) label.append(node("span", "field-hint", ` (${field.hint})`));
  // dopiski i przycisk „cofnij” obok etykiety, nie w niej (opis rubryki przez aria-describedby)
  const tags = node("span", "field-tags");
  head.append(label, tags);
  const error = node("p", "field-error");
  error.id = `${id}-error`;
  error.hidden = true;
  const tag = (className, text) => Object.assign(node("span", className, text), { id: `${id}-info` });
  let targets = [];   // elementy z aria-describedby / aria-invalid

  const updateTags = () => {
    tags.replaceChildren();
    const current = getPath(dataAt(index), path);
    if (isEdited(index, path)) {
      tags.append(tag("field-edited", "poprawione"));
      const undo = node("button", "link-btn", "cofnij");
      undo.type = "button";
      undo.setAttribute("aria-label", `Cofnij poprawkę: ${field.label}`);
      undo.addEventListener("click", (event) => {
        event.preventDefault();
        setValue(index, path, structuredClone(getPath(state.results[index].data, path) ?? null));
        renderSheet();
        refreshAfterEdit(index);
      });
      tags.append(undo);
    } else if (isEmptyValue(current)) {
      tags.append(tag("field-note", "brak w dokumencie"));
    } else {
      const source = ctx.evidence.get(path);
      if (source?.page) {
        // klikalne źródło: strona w podglądzie i podświetlony fragment
        const b = Object.assign(node("button", "link-btn field-source", source.label), { id: `${id}-info`, type: "button" });
        b.title = "Pokaż w podglądzie PDF";
        b.setAttribute("aria-label", `Źródło: ${source.label}. Pokaż w podglądzie PDF`);
        b.addEventListener("click", (event) => {
          event.preventDefault();
          showSource(index, source.page, source.text ?? current);
        });
        tags.append(b);
      } else if (source?.label) tags.append(tag("field-source", source.label));
    }
  };

  /** Zapis wartości (lub błąd walidacji) z pola edycji. */
  // problem = błąd (wartość nie jest zapisywana); warn = ostrzeżenie (wartość zapisana)
  const commit = (value, problem = null, warn = false) => {
    error.hidden = !problem;
    error.textContent = problem ?? "";
    error.dataset.kind = warn ? "warn" : "error";
    wrap.dataset.invalid = String(Boolean(problem) && !warn);
    targets.forEach((t) => t.setAttribute("aria-invalid", String(Boolean(problem) && !warn)));
    if (problem && !warn) return;
    setValue(index, path, value);
    updateTags();
    refreshAfterEdit(index);
  };

  const control = controlFor(field, value, id, commit, path);
  const box = control.element;
  targets = box.matches("input, textarea, [role=radiogroup]") ? [box] : [...box.querySelectorAll("input, textarea")];
  targets.forEach((t) => t.setAttribute("aria-describedby", `${id}-info ${id}-error`));
  wrap.append(head, box, error);
  // wartość od modelu też sprawdzamy sumą kontrolną (bez zapisu: to tylko ostrzeżenie)
  if (checksumValid(path, value) === false) {
    error.hidden = false;
    error.textContent = CHECKSUM_WARNING;
    error.dataset.kind = "warn";
  }
  const activate = () => {
    if (state.active?.path === path && state.active.index === index) return;
    state.active = { index, path, field, apply: control.apply, wrap };
    el.sheet.querySelectorAll(".field[data-active]").forEach((f) => f.removeAttribute("data-active"));
    wrap.dataset.active = "true";
    el.sheet.querySelectorAll(".pdfv").forEach((v) => { v.dataset.target = field.label; });
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
    case "date": return dateControl(value, id, commit, field.label);
    case "bool": return choiceControl([["1", "tak", 1], ["0", "nie", 0], ["", "brak informacji", null]], value === true ? 1 : value === false ? 0 : value ?? null, id, commit);
    case "enum": return choiceControl([...Object.entries(field.labels ?? {}).map(([v, t]) => [v, t, v]), ["", "brak informacji", null]], value ?? null, id, commit);
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
    const cell = (i) => {
      const c = node("i", null, chars[i] ?? "");
      if (!chars[i]) c.className = "is-empty";
      if (i === caret) c.classList.add("is-caret");
      return c;
    };
    const range = (a, b) => Array.from({ length: Math.max(0, b - a) }, (_, k) => cell(a + k));
    if (gaps.length) {
      // grupy (rachunek) łamią się w całości: w wąskiej kolumnie przenosi się cała czwórka cyfr
      const bounds = [0, ...gaps.filter((g) => g < count), count];
      row.replaceChildren(...bounds.slice(1).map((end, k) => {
        const grp = node("span", "cells-grp");
        grp.append(...range(bounds[k], end));
        return grp;
      }));
    } else {
      row.replaceChildren(...range(0, count));
    }
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
    const value = field.integer ? Number(digits) : digits;
    // suma kontrolna (NIP, REGON, PESEL, rachunek): ostrzeżenie, wartość i tak zostaje zapisana
    if (checksumValid(path, digits) === false) return commit(value, CHECKSUM_WARNING, true);
    commit(value);
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
function dateControl(value, id, commit, fieldLabel) {
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
    input.setAttribute("aria-label", `${fieldLabel}: ${label}`);   // sam „rok” nie mówi, której daty dotyczy
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
function choiceControl(options, value, id, commit) {
  const group = node("div", "choices");
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-labelledby", `${id}-label`);
  const name = `${id}-r`;
  options.forEach(([v, text, stored]) => {
    const lab = node("label", "choice");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = v;
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
  input.placeholder = " ";   // pusta rubryka jest zakreskowana jak puste kratki (:placeholder-shown)
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
  input.placeholder = " ";
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
const SVG_NS = "http://www.w3.org/2000/svg";
const insertArrow = document.createElementNS(SVG_NS, "svg");
insertArrow.classList.add("insert-arrow");
insertArrow.setAttribute("aria-hidden", "true");
insertArrow.innerHTML = '<defs><marker id="insert-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1.5 8 5 1 8.5"/></marker></defs><line marker-end="url(#insert-head)"/><circle r="2.5"/>';
insertArrow.style.display = "none";
document.body.append(insertArrow, insertBtn);
let pendingSelection = "";

function hideInsertButton() {
  insertBtn.hidden = true;
  insertArrow.style.display = "none";
  pendingSelection = "";
}

document.addEventListener("mouseup", (event) => {
  if (event.target === insertBtn) return;
  const inPdf = event.target.closest?.(".pdfv-stage");
  const selection = window.getSelection();
  const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
  if (!inPdf || !text) { hideInsertButton(); return; }
  const sel = selection.getRangeAt(0).getBoundingClientRect();
  const ready = state.active && state.active.index === state.selected && state.sheetMode === "fields";
  pendingSelection = text;
  insertBtn.textContent = ready ? `Wstaw do: ${state.active.field.label}` : "Najpierw kliknij rubrykę po lewej";
  insertBtn.disabled = !ready;
  insertBtn.hidden = false;
  const pane = inPdf.getBoundingClientRect();
  const place = insertPlacement(sel, pane, { width: insertBtn.offsetWidth, height: insertBtn.offsetHeight },
    { width: window.innerWidth, height: window.innerHeight });
  insertBtn.style.left = `${place.button.left}px`;
  insertBtn.style.top = `${place.button.top}px`;
  // cienka strzałka w kolorze akcentu: od zaznaczenia do przycisku (tylko gdy jest dokąd wstawić)
  if (ready && place.arrow) {
    const line = insertArrow.querySelector("line");
    const dot = insertArrow.querySelector("circle");
    line.setAttribute("x1", place.arrow.x1); line.setAttribute("y1", place.arrow.y1);
    line.setAttribute("x2", place.arrow.x2); line.setAttribute("y2", place.arrow.y2);
    dot.setAttribute("cx", place.arrow.x1); dot.setAttribute("cy", place.arrow.y1);
    insertArrow.style.display = "";
  } else {
    insertArrow.style.display = "none";
  }
});
insertBtn.addEventListener("mousedown", (event) => event.preventDefault());   // nie gubimy zaznaczenia
insertBtn.addEventListener("click", () => {
  if (!state.active || !pendingSelection) return;
  state.active.apply(pendingSelection);
  window.getSelection()?.removeAllRanges();
  hideInsertButton();
});
document.addEventListener("scroll", hideInsertButton, true);

/* to samo z klawiatury: Alt+↓ w rubryce → podgląd PDF, strzałki wybierają wiersz, Enter wstawia */

function leavePdfFull() {
  if (!state.pdfFull) return;
  state.pdfFull = false;
  const body = el.sheet.querySelector(".sheet-body");
  if (body) body.dataset.full = "false";
  el.sheet.querySelector(".pdfv-full")?.setAttribute("aria-pressed", "false");
}

/** Fokus z powrotem na ostatnią rubrykę (zaznaczona opcja, pole albo pierwsza kratka). */
function focusActiveField() {
  leavePdfFull();
  const wrap = state.active?.wrap?.isConnected ? state.active.wrap : el.sheet.querySelector(".fields-pane .field");
  wrap?.querySelector("input[type=radio]:checked, input:not([type=radio]), textarea, input[type=radio]")?.focus();
}

document.addEventListener("keydown", (event) => {
  if (!event.altKey || event.key !== "ArrowDown" || !event.target.closest?.(".fields-pane")) return;
  const stage = el.sheet.querySelector(".pdfv-stage");
  event.preventDefault();
  if (stage) stage.focus();
  else announce("Podgląd PDF jest ukryty. Włącz go w menu „Opcje dokumentu”.");
});

document.addEventListener("pdf-pick", (event) => {
  const ready = state.active && state.active.index === state.selected && state.sheetMode === "fields";
  if (!ready) {
    announce("Najpierw wybierz rubrykę po lewej, potem wróć do podglądu klawiszami Alt+↓.");
    return;
  }
  const { field, wrap } = state.active;
  leavePdfFull();
  state.active.apply(event.detail);
  if (!wrap.contains(document.activeElement)) focusActiveField();
  const problem = wrap.querySelector(".field-error:not([hidden])");
  announce(problem?.textContent ? `${field.label}: ${problem.textContent}` : `Wstawiono do rubryki: ${field.label}.`);
});
document.addEventListener("pdf-back", focusActiveField);

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
      // pola zgrupowane po sekcji („Odwołujący: Nazwa” → wiersz „Odwołujący” z listą pól), bez chmury etykiet
      const groups = new Map();
      t.fields.forEach((f) => {
        const text = typeof f === "string" ? f : f.label ?? f.name ?? String(f);
        const cut = text.indexOf(": ");
        const [group, name] = cut > 0 ? [text.slice(0, cut), text.slice(cut + 2)] : ["", text];
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(name);
      });
      const dl = node("dl", "type-fields");
      groups.forEach((names, group) => {
        const row = node("div");
        row.append(node("dt", null, group || "Pola"), node("dd", null, names.join(", ")));
        dl.append(row);
      });
      card.append(dl);
    }
    return card;
  }));
}

/* ---------- JSON i pobieranie ---------- */

function jsonView(data) {
  const pre = node("pre", "json");
  pre.tabIndex = 0;
  pre.setAttribute("role", "region");   // przewijany obszar z klawiatury, z nazwą dla czytnika
  pre.setAttribute("aria-label", "Dane dokumentu w formacie JSON");
  JSON.stringify(data, null, 2).split(/("(?:[^"\\]|\\.)*"(?=\s*:)|\bnull\b)/g).forEach((part) => {
    if (/^".*"$/.test(part)) pre.append(node("span", "k", part));
    else if (part === "null") pre.append(node("span", "n", part));
    else pre.append(part);
  });
  return pre;
}


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

/** Nazwa pliku, którą da się złamać po „_” i „-” albo przed rozszerzeniem zamiast w środku słowa. */
function fileNameNode(tag, className, name) {
  const n = node(tag, className);
  name.split(/(?<=[_\-])/).forEach((part, i) => {
    if (i) n.append(document.createElement("wbr"));
    n.append(part);
  });
  return n;
}

function node(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
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
