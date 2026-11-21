// Podgląd PDF strona po stronie, z warstwą tekstu do zaznaczania (PDF.js, Apache-2.0,
// pliki w vendor/pdfjs). Strona mieści się w panelu; przewijania nie ma, dopóki
// użytkownik nie powiększy. Gdy PDF.js zawiedzie, wracamy do wbudowanej przeglądarki.

let pdfjsPromise = null;

function loadPdfJs() {
  pdfjsPromise ??= import("./vendor/pdfjs/pdf.min.js").then((lib) => {
    lib.GlobalWorkerOptions.workerSrc = new URL("./vendor/pdfjs/pdf.worker.min.js", import.meta.url).href;
    return lib;
  });
  return pdfjsPromise;
}

// 0 = cała strona, 1 = szerokość panelu (domyślnie), dalej powiększenia szerokości
const ZOOM_LABELS = ["Cała strona", "Szerokość", "125%", "150%", "200%"];
const WIDTH_FACTORS = [null, 1, 1.25, 1.5, 2];

/** @returns {{ element: HTMLElement }} element do wstawienia w panel podglądu */
export function createPdfViewer(file, url, title) {
  const element = document.createElement("div");
  element.className = "pdfv";
  element.innerHTML = `
    <div class="pdfv-bar">
      <button type="button" class="pdfv-btn" data-act="prev" aria-label="Poprzednia strona"><svg class="ic" aria-hidden="true"><use href="#i-prev"/></svg></button>
      <span class="pdfv-page-no" aria-live="polite">Strona –</span>
      <button type="button" class="pdfv-btn" data-act="next" aria-label="Następna strona"><svg class="ic" aria-hidden="true"><use href="#i-next"/></svg></button>
      <span class="pdfv-sep"></span>
      <button type="button" class="pdfv-btn" data-act="out" aria-label="Pomniejsz"><svg class="ic" aria-hidden="true"><use href="#i-minus"/></svg></button>
      <span class="pdfv-zoom" aria-live="polite">Szerokość</span>
      <button type="button" class="pdfv-btn" data-act="in" aria-label="Powiększ"><svg class="ic" aria-hidden="true"><use href="#i-plus"/></svg></button>
      <button type="button" class="pdfv-btn pdfv-full" data-act="full" aria-pressed="false" aria-label="Powiększ podgląd na cały obszar" title="Powiększ podgląd na cały obszar"><svg class="ic" aria-hidden="true"><use href="#i-expand"/></svg></button>
    </div>
    <p class="pdfv-status">Wczytywanie podglądu…</p>
    <p class="sr-only pdfv-live" aria-live="polite"></p>
    <div class="pdfv-stage" tabindex="0"></div>`;
  const stage = element.querySelector(".pdfv-stage");
  stage.setAttribute("role", "region");
  stage.setAttribute("aria-label", `${title}. Strzałki w górę i w dół wybierają wiersz tekstu, `
    + "Enter wstawia go do wybranej rubryki, Escape wraca do rubryki, Page Up i Page Down zmieniają stronę.");
  const live = element.querySelector(".pdfv-live");
  const status = element.querySelector(".pdfv-status");
  const pageNo = element.querySelector(".pdfv-page-no");
  const view = { doc: null, lib: null, page: 1, zoom: 1, rendering: null, hasText: true };
  const zoomLabel = element.querySelector(".pdfv-zoom");

  const draw = async () => {
    if (!view.doc || !stage.isConnected || stage.clientWidth === 0) return;
    const token = {};
    view.rendering = token;
    const page = await view.doc.getPage(view.page);
    const keepTop = stage.scrollTop;
    const base = page.getViewport({ scale: 1 });
    // dopasowanie całej strony do panelu, potem ewentualne powiększenie
    const fitWidth = (stage.clientWidth - 24) / base.width;
    const fitPage = Math.min(fitWidth, (stage.clientHeight - 16) / base.height);
    const scale = view.zoom === 0 ? fitPage : fitWidth * WIDTH_FACTORS[view.zoom];
    const viewport = page.getViewport({ scale: Math.max(0.3, scale) });
    const ratio = window.devicePixelRatio || 1;

    const wrap = document.createElement("div");
    wrap.className = "pdfv-page";
    wrap.style.width = `${viewport.width}px`;
    wrap.style.height = `${viewport.height}px`;
    wrap.style.setProperty("--scale-factor", viewport.scale);
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    canvas.setAttribute("aria-hidden", "true");
    const textLayer = document.createElement("div");
    textLayer.className = "textLayer";
    wrap.append(canvas, textLayer);

    await page.render({
      canvasContext: canvas.getContext("2d"), viewport,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
    }).promise;
    const textContent = await page.getTextContent();
    if (view.rendering !== token) return;     // w międzyczasie zmieniono stronę
    stage.replaceChildren(wrap);
    stage.scrollTop = keepTop;
    await new view.lib.TextLayer({ textContentSource: textContent, container: textLayer, viewport }).render();

    const chars = textContent.items.reduce((s, it) => s + (it.str?.trim().length ?? 0), 0);
    pageNo.textContent = `Strona ${view.page} z ${view.doc.numPages}`;
    element.querySelector('[data-act="prev"]').disabled = view.page <= 1;
    element.querySelector('[data-act="next"]').disabled = view.page >= view.doc.numPages;
    element.querySelector('[data-act="out"]').disabled = view.zoom === 0;
    element.querySelector('[data-act="in"]').disabled = view.zoom === ZOOM_LABELS.length - 1;
    zoomLabel.textContent = ZOOM_LABELS[view.zoom];
    stage.dataset.zoomed = String(view.zoom > 0);
    status.dataset.kind = chars > 0 ? "text" : "scan";
    pick.lines = null;          // nowa strona albo skala: wiersze liczymy od nowa
    pick.cursor = pick.anchor = -1;
    showHint();
    if (view.mark) markSource(view.mark);
  };

  /* ---------- źródło pola: strona z evidence i podświetlony fragment ---------- */

  /** Tekst do porównań: małe litery, bez polskich znaków, odstępów i interpunkcji. */
  const norm = (t) => String(t ?? "").normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/ł/gi, "l")
    .toLowerCase().replace(/[^a-z0-9@]/g, "");
  /** Warianty szukanego tekstu: data ISO szukana też jako DD.MM.RRRR. */
  const variants = (t) => {
    const out = [norm(t)];
    const iso = String(t).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (iso) out.push(norm(`${iso[3]}${iso[2]}${iso[1]}`));
    return out.filter((v) => v.length >= 2);
  };
  function markSource(text) {
    stage.querySelectorAll(".is-source").forEach((s) => s.classList.remove("is-source"));
    const wanted = variants(text);
    if (!wanted.length || !hasText()) return;
    const lines = collectLines();
    const hits = lines.filter((line) => wanted.some((w) => norm(line.text).includes(w)));
    hits.forEach((line) => line.spans.forEach((s) => s.classList.add("is-source")));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // przewijamy tylko podgląd (scrollIntoView przesunąłby też całą stronę panelu)
    const first = hits[0]?.spans[0];
    if (first && stage.scrollHeight > stage.clientHeight) {
      const r = first.getBoundingClientRect(), box = stage.getBoundingClientRect();
      stage.scrollTo({ top: stage.scrollTop + r.top - box.top - stage.clientHeight / 2, behavior: reduce ? "auto" : "smooth" });
    }
  }

  /** Przejście do strony z evidence i podświetlenie fragmentu (tekst z evidence albo wartość pola). */
  element.showSource = async (pageNumber, text) => {
    await ready;
    if (!view.doc) return;
    view.page = Math.min(view.doc.numPages, Math.max(1, Number(pageNumber) || 1));
    view.mark = text ?? null;
    await draw();
  };

  /* ---------- wybór wiersza z klawiatury (odpowiednik zaznaczania myszą) ---------- */

  const pick = { lines: null, cursor: -1, anchor: -1 };
  const hasText = () => status.dataset.kind === "text";

  /** Wiersze strony z warstwy tekstu: fragmenty o tej samej wysokości, od lewej do prawej. */
  const collectLines = () => {
    const items = [...stage.querySelectorAll(".textLayer span")]
      .filter((s) => !s.querySelector("span") && s.textContent.trim())
      .map((s) => ({ s, r: s.getBoundingClientRect() }))
      .sort((a, b) => a.r.top - b.r.top || a.r.left - b.r.left);
    const lines = [];
    for (const it of items) {
      const line = lines.at(-1);
      if (line && Math.abs(it.r.top - line.top) < Math.max(3, it.r.height / 2)) line.items.push(it);
      else lines.push({ top: it.r.top, items: [it] });
    }
    return lines.map(({ items: row }) => {
      row.sort((a, b) => a.r.left - b.r.left);
      let text = "";
      row.forEach((it, i) => { text += (i && it.r.left - row[i - 1].r.right > 1 ? " " : "") + it.s.textContent; });
      return { spans: row.map((it) => it.s), text: text.replace(/\s+/g, " ").trim() };
    });
  };

  const range = () => {
    if (pick.cursor < 0 || !pick.lines) return [];
    const [a, b] = [Math.min(pick.anchor, pick.cursor), Math.max(pick.anchor, pick.cursor)];
    return pick.lines.slice(a, b + 1);
  };
  const paintPick = (on = true) => {
    stage.querySelectorAll(".is-picked").forEach((s) => s.classList.remove("is-picked"));
    if (!on) return;
    range().forEach((line) => line.spans.forEach((s) => s.classList.add("is-picked")));
    pick.lines?.[pick.cursor]?.spans[0]?.scrollIntoView({ block: "nearest", inline: "nearest" });
  };
  const say = (text) => { live.textContent = ""; setTimeout(() => { live.textContent = text; }, 30); };

  /** Podpowiedź w pasku stanu: inna, gdy podgląd ma fokus z klawiatury. */
  function showHint() {
    if (!hasText()) {
      status.textContent = "Ta strona to skan bez warstwy tekstu: wartości trzeba wpisać ręcznie.";
      return;
    }
    const target = element.dataset.target;
    status.textContent = document.activeElement === stage
      ? `↑/↓: wiersz · Shift+↑/↓: kilka wierszy · Enter: wstaw ${target ? `do „${target}”` : "do wybranej rubryki"} · Esc: wróć do rubryki`
      : "Zaznacz w dokumencie tekst, żeby wstawić go do wybranej rubryki.";
  }
  stage.addEventListener("focus", () => { showHint(); paintPick(); });
  // przejście do innego okna też wywołuje blur: wybór znika dopiero, gdy fokus naprawdę opuści podgląd
  stage.addEventListener("blur", () => setTimeout(() => {
    if (document.activeElement !== stage) { showHint(); paintPick(false); }
  }));

  stage.addEventListener("keydown", (event) => {
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && !event.altKey) {
      event.preventDefault();
      if (!hasText()) { say("Na tej stronie nie ma tekstu do wybrania."); return; }
      pick.lines ??= collectLines();
      const n = pick.lines.length;
      if (!n) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      pick.cursor = pick.cursor < 0 ? (step > 0 ? 0 : n - 1) : Math.min(n - 1, Math.max(0, pick.cursor + step));
      if (!event.shiftKey || pick.anchor < 0) pick.anchor = pick.cursor;
      paintPick();
      const lines = range();
      say(lines.length > 1
        ? `Wybrano ${lines.length} ${lines.length % 10 >= 2 && lines.length % 10 <= 4 && (lines.length % 100 < 12 || lines.length % 100 > 14) ? "wiersze" : "wierszy"}: ${lines.map((l) => l.text).join(" ")}`
        : `Wiersz ${pick.cursor + 1} z ${n}: ${lines[0].text}`);
    } else if (event.key === "Enter") {
      const text = range().map((l) => l.text).join(" ");
      if (!text) return;
      event.preventDefault();
      element.dispatchEvent(new CustomEvent("pdf-pick", { bubbles: true, detail: text }));
    } else if (event.key === "Escape" || (event.altKey && event.key === "ArrowUp")) {
      event.preventDefault();
      element.dispatchEvent(new CustomEvent("pdf-back", { bubbles: true }));
    }
  });

  element.addEventListener("click", (event) => {
    const act = event.target.closest?.("[data-act]")?.dataset.act;
    if (!act || !view.doc) return;
    if (act === "prev" && view.page > 1) view.page -= 1;
    if (act === "next" && view.page < view.doc.numPages) view.page += 1;
    if (act === "full") {
      const on = event.target.closest("[data-act]").getAttribute("aria-pressed") !== "true";
      event.target.closest("[data-act]").setAttribute("aria-pressed", String(on));
      element.dispatchEvent(new CustomEvent("pdf-full", { bubbles: true, detail: on }));
      return;
    }
    if (act === "in" && view.zoom < ZOOM_LABELS.length - 1) view.zoom += 1;
    if (act === "out" && view.zoom > 0) view.zoom -= 1;
    draw();
  });
  stage.addEventListener("keydown", (event) => {
    if (event.key === "PageDown" || (event.key === "ArrowRight" && view.zoom === 0)) element.querySelector('[data-act="next"]').click();
    if (event.key === "PageUp" || (event.key === "ArrowLeft" && view.zoom === 0)) element.querySelector('[data-act="prev"]').click();
  });

  // ponowne dopasowanie, gdy panel zmieni rozmiar albo zostanie pokazany
  let timer = null;
  new ResizeObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(draw, 120);
  }).observe(stage);

  let markReady;
  const ready = new Promise((resolve) => { markReady = resolve; });
  (async () => {
    try {
      view.lib = await loadPdfJs();
      view.doc = await view.lib.getDocument({ data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false }).promise;
      await draw();
      markReady();
    } catch (error) {
      markReady();
      console.warn("PDF.js niedostępny, używam wbudowanej przeglądarki:", error);
      element.querySelector(".pdfv-bar").hidden = true;
      status.textContent = "Zaznaczanie tekstu niedostępne dla tego pliku. Poniżej zwykły podgląd.";
      const frame = document.createElement("iframe");
      frame.className = "pdf-frame";
      frame.src = `${url}#view=FitH&navpanes=0`;
      frame.title = title;
      stage.replaceChildren(frame);
    }
  })();

  return { element };
}
