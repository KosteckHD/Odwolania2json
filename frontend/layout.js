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
 * Położenie przycisku „Wstaw do: …” i strzałki od zaznaczenia w PDF-ie do przycisku.
 * Przycisk staje przy lewej krawędzi podglądu (od strony rubryk), na wysokości zaznaczenia;
 * gdy zaznaczenie leży tuż przy krawędzi, przycisk schodzi pod zaznaczenie, a strzałka idzie w dół.
 * Wszystkie współrzędne w pikselach okna (jak getBoundingClientRect).
 * @param {{left:number, top:number, right:number, bottom:number}} sel prostokąt zaznaczenia
 * @param {{left:number, top:number, right:number, bottom:number}} pane prostokąt podglądu PDF
 * @param {{width:number, height:number}} button rozmiar przycisku
 * @param {{width:number, height:number}} view rozmiar okna
 * @returns {{button:{left:number, top:number}, arrow:{x1:number, y1:number, x2:number, y2:number}|null}}
 */
export function insertPlacement(sel, pane, button, view, { margin = 8, gap = 36 } = {}) {
  const clampX = (x) => Math.max(margin, Math.min(view.width - button.width - margin, x));
  const clampY = (y) => Math.max(margin, Math.min(view.height - button.height - margin, y));
  const midY = (sel.top + sel.bottom) / 2;
  const sideLeft = clampX(pane.left + 10);
  // obok: od lewej krawędzi zaznaczenia w lewo do przycisku
  if (sel.left - (sideLeft + button.width) >= gap) {
    const top = clampY(midY - button.height / 2);
    return {
      button: { left: sideLeft, top },
      arrow: { x1: sel.left - 4, y1: midY, x2: sideLeft + button.width + 6, y2: top + button.height / 2 },
    };
  }
  // pod spodem: krótka strzałka w dół od zaznaczenia
  const left = clampX(sel.left);
  const below = sel.bottom + gap;
  const top = below + button.height + margin <= view.height ? below : clampY(sel.top - gap - button.height);
  const x = Math.min(Math.max(left + 14, sel.left + 6), left + button.width - 6);
  const down = top > sel.bottom;
  return {
    button: { left, top },
    arrow: down
      ? { x1: x, y1: sel.bottom + 3, x2: x, y2: top - 5 }
      : { x1: x, y1: sel.top - 3, x2: x, y2: top + button.height + 5 },
  };
}
