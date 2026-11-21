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
      <button type="button" class="pdfv-btn" data-act="prev" aria-label="Poprzednia strona">‹</button>
      <span class="pdfv-page-no" aria-live="polite">Strona –</span>
      <button type="button" class="pdfv-btn" data-act="next" aria-label="Następna strona">›</button>
      <span class="pdfv-sep"></span>
      <button type="button" class="pdfv-btn" data-act="out" aria-label="Pomniejsz">−</button>
      <span class="pdfv-zoom" aria-live="polite">Szerokość</span>
      <button type="button" class="pdfv-btn" data-act="in" aria-label="Powiększ">+</button>
      <button type="button" class="pdfv-btn pdfv-full" data-act="full" aria-pressed="false" aria-label="Powiększ podgląd na cały obszar" title="Powiększ podgląd na cały obszar">⤢</button>
    </div>
    <p class="pdfv-status">Wczytywanie podglądu…</p>
    <div class="pdfv-stage" tabindex="0"></div>`;
  const stage = element.querySelector(".pdfv-stage");
  stage.setAttribute("aria-label", title);
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
    status.textContent = chars > 0
      ? "Zaznacz w dokumencie tekst, żeby wstawić go do wybranej rubryki."
      : "Ta strona to skan bez warstwy tekstu: wartości trzeba wpisać ręcznie.";
  };

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

  (async () => {
    try {
      view.lib = await loadPdfJs();
      view.doc = await view.lib.getDocument({ data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false }).promise;
      await draw();
    } catch (error) {
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
