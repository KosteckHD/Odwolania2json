// Czyste funkcje układu panelu (bez DOM): opisy pasków, statusy, położenie przycisku „Wstaw do”.
// Testy: tests/layout.test.mjs.
import { plural } from "./draft.js";

/** Status pliku → tekst i ikona (ikona jest tylko dodatkiem: status zawsze ma tekst). */
export const STATUS = {
  selected: { text: "Czeka na przetworzenie", icon: "wait" },
  queued: { text: "W kolejce", icon: "wait" },
  pending: { text: "Przetwarzanie…", icon: "pending" },
  ok: { text: "Rozpoznany", icon: "ok" },
  unknown: { text: "Nie rozpoznano", icon: "unknown" },
  error: { text: "Błąd", icon: "error" },
};

/**
 * Podpis przycisku „Dokumenty ▾”: liczba plików i to, co wymaga uwagi
 * (błędy, nierozpoznane, przetwarzane). Widoczny także przy zamkniętym panelu.
 * @param {string[]} statuses status każdego pliku (ok, unknown, error, pending, selected)
 */
export function docsSummary(statuses) {
  const count = (s) => statuses.filter((x) => x === s).length;
  const parts = [];
  const waiting = count("pending") + count("queued");
  const errors = count("error");
  const unknown = count("unknown");
  // w trakcie przetwarzania: „2 z 5 gotowe”
  const progress = waiting ? `${statuses.length - waiting} z ${statuses.length} gotowe` : "";
  if (progress) parts.push(progress);
  if (errors) parts.push(`${errors} ${plural(errors, "błąd", "błędy", "błędów")}`);
  if (unknown) parts.push(`${unknown} ${plural(unknown, "nierozpoznany", "nierozpoznane", "nierozpoznanych")}`);
  return { count: statuses.length, attention: parts.join(", "), alert: errors > 0, progress };
}

/** „16/22 pól” i „1 poprawka” dla prawej strony drugiego paska. */
export function progressText(completeness, edits) {
  const parts = [];
  if (completeness) parts.push(`${completeness.filled}/${completeness.total} pól`);
  if (edits) parts.push(`${edits} ${plural(edits, "poprawka", "poprawki", "poprawek")}`);
  return parts.join(" · ");
}

/** „odwolanie.pdf · 1 z 5” do środka drugiego paska. */
export function positionText(name, index, total) {
  return `${name} · ${index + 1} z ${total}`;
}

/**
 * Położenie przycisku „Wstaw do: …” i strzałki od przycisku do zaznaczenia w PDF-ie (jak na mockupie:
 * obrysowana etykieta nad zaznaczeniem i po jego prawej, cienka strzałka ukośnie w dół do końca zaznaczenia).
 * Kolejność prób: po prawej, po lewej, a gdy po bokach brak miejsca — pod zaznaczeniem (albo nad nim przy dole okna).
 * Wszystkie współrzędne w pikselach okna (jak getBoundingClientRect).
 * @param {{left:number, top:number, right:number, bottom:number}} sel prostokąt zaznaczenia
 * @param {{left:number, top:number, right:number, bottom:number}} pane prostokąt podglądu PDF
 * @param {{width:number, height:number}} button rozmiar przycisku
 * @param {{width:number, height:number}} view rozmiar okna
 * @returns {{button:{left:number, top:number}, side:"right"|"left"|"below"|"above",
 *   arrow:{x1:number, y1:number, x2:number, y2:number}}} strzałka: (x1, y1) przy przycisku, grot w (x2, y2) przy zaznaczeniu
 */
export function insertPlacement(sel, pane, button, view, { margin = 8, gap = 44, rise = 26 } = {}) {
  const clampX = (x) => Math.max(margin, Math.min(view.width - button.width - margin, x));
  const clampY = (y) => Math.max(margin, Math.min(view.height - button.height - margin, y));
  const midY = (sel.top + sel.bottom) / 2;
  const minLeft = Math.max(margin, pane.left + margin);
  const maxRight = Math.min(view.width - margin, pane.right - margin);
  // etykieta trochę wyżej niż zaznaczenie, żeby strzałka szła ukośnie, jak na mockupie
  const top = clampY(sel.top - rise - button.height / 2);
  const startY = Math.min(top + button.height - 4, Math.max(top + 4, midY));

  const right = sel.right + gap;
  if (right + button.width <= maxRight) {
    return { side: "right", button: { left: right, top },
      arrow: { x1: right - 2, y1: startY, x2: sel.right + 5, y2: midY } };
  }
  const left = sel.left - gap - button.width;
  if (left >= minLeft) {
    return { side: "left", button: { left, top },
      arrow: { x1: left + button.width + 2, y1: startY, x2: sel.left - 5, y2: midY } };
  }
  // brak miejsca po bokach: pod zaznaczeniem, a przy dole okna nad nim; strzałka pionowa do zaznaczenia
  const bx = clampX(Math.min(sel.left, maxRight - button.width));
  const below = sel.bottom + gap;
  const down = below + button.height + margin <= view.height;
  const by = down ? below : clampY(sel.top - gap - button.height);
  const x = Math.min(Math.max(bx + 16, sel.left + 8), bx + button.width - 8);
  return { side: down ? "below" : "above", button: { left: bx, top: by },
    arrow: down ? { x1: x, y1: by - 2, x2: x, y2: sel.bottom + 4 }
                : { x1: x, y1: by + button.height + 2, x2: x, y2: sel.top - 4 } };
}

/**
 * Przesuwa etykietę „Wstaw do” z tekstu PDF-u na wolne miejsce (jak na mockupie: etykieta stoi obok wierszy,
 * nie na nich). Najpierw w prawo za zasłaniane wiersze, a gdy brak miejsca — w górę o wysokość etykiety.
 * Grot strzałki zostaje przy zaznaczeniu; zmienia się tylko jej początek.
 * @param {ReturnType<typeof insertPlacement>} place wynik insertPlacement
 * @param {Array<{left:number, top:number, right:number, bottom:number}>} boxes prostokąty wierszy tekstu
 * @param {{width:number, height:number}} button rozmiar etykiety
 * @param {{left:number, right:number, top:number}} limits obszar, w którym etykieta może stać
 */
export function avoidText(place, boxes, button, limits, { pad = 10, tries = 4 } = {}) {
  if (place.side !== "right" && place.side !== "left") return place;
  let { left, top } = place.button;
  const hits = (l, t) => boxes.filter((b) => b.right > l - pad && b.left < l + button.width + pad
    && b.bottom > t - 2 && b.top < t + button.height + 2);
  for (let i = 0; i < tries; i++) {
    const over = hits(left, top);
    if (!over.length) break;
    const shifted = Math.max(...over.map((b) => b.right)) + pad;
    if (place.side === "right" && shifted + button.width <= limits.right) left = shifted;
    else top = Math.max(limits.top, top - button.height - 4);
  }
  if (left === place.button.left && top === place.button.top) return place;
  const midY = place.arrow.y2;
  const y1 = Math.min(top + button.height - 4, Math.max(top + 4, midY));
  const x1 = place.side === "right" ? left - 2 : left + button.width + 2;
  return { ...place, button: { left, top }, arrow: { ...place.arrow, x1, y1 } };
}
