// Testy czystych funkcji układu (layout.js): podpisy pasków, statusy, położenie „Wstaw do” i strzałki.
import { test } from "node:test";
import assert from "node:assert/strict";
import { STATUS, docsSummary, insertPlacement, positionText, progressText } from "../layout.js";

test("STATUS: każdy status ma tekst i ikonę (status nigdy samym kolorem)", () => {
  for (const key of ["selected", "pending", "ok", "unknown", "error"]) {
    assert.ok(STATUS[key].text.length > 0, key);
    assert.ok(STATUS[key].icon.length > 0, key);
  }
  assert.equal(STATUS.error.text, "Błąd");
  assert.equal(STATUS.unknown.text, "Nie rozpoznano");
});

test("docsSummary: liczba plików i to, co wymaga uwagi, z polską odmianą", () => {
  assert.deepEqual(docsSummary(["ok", "ok", "ok"]), { count: 3, attention: "", alert: false });
  assert.deepEqual(docsSummary(["ok", "error", "unknown", "ok", "ok"]),
    { count: 5, attention: "1 błąd, 1 nierozpoznany", alert: true });
  assert.equal(docsSummary(["error", "error", "ok"]).attention, "2 błędy");
  assert.equal(docsSummary(Array(5).fill("error")).attention, "5 błędów");
  assert.equal(docsSummary(["unknown", "unknown"]).attention, "2 nierozpoznane");
  assert.equal(docsSummary(["pending", "ok"]).attention, "przetwarzanie: 1");
  assert.equal(docsSummary(["unknown"]).alert, false);
});

test("progressText i positionText: prawa i środkowa część drugiego paska", () => {
  assert.equal(progressText({ filled: 16, total: 22 }, 0), "16/22 pól");
  assert.equal(progressText({ filled: 16, total: 22 }, 1), "16/22 pól · 1 poprawka");
  assert.equal(progressText({ filled: 5, total: 6 }, 3), "5/6 pól · 3 poprawki");
  assert.equal(progressText(null, 5), "5 poprawek");
  assert.equal(progressText(null, 0), "");
  assert.equal(positionText("odwolanie.pdf", 0, 5), "odwolanie.pdf · 1 z 5");
});

const view = { width: 1440, height: 900 };
const pane = { left: 700, top: 150, right: 1440, bottom: 900 };
const button = { width: 180, height: 32 };

test("insertPlacement: zaznaczenie daleko od krawędzi → przycisk przy lewej krawędzi podglądu, strzałka w lewo", () => {
  const sel = { left: 1100, top: 400, right: 1250, bottom: 416 };
  const { button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.equal(b.left, 710);
  assert.equal(b.top, 408 - 16);
  // strzałka zaczyna się przy zaznaczeniu i kończy za prawą krawędzią przycisku
  assert.equal(arrow.x1, 1096);
  assert.equal(arrow.y1, 408);
  assert.ok(arrow.x2 > b.left + button.width && arrow.x2 < sel.left);
  assert.equal(arrow.y2, b.top + button.height / 2);
});

test("insertPlacement: zaznaczenie przy krawędzi → przycisk pod spodem, strzałka w dół", () => {
  const sel = { left: 760, top: 240, right: 950, bottom: 254 };
  const { button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.equal(b.left, 760);
  assert.ok(b.top > sel.bottom);
  assert.equal(arrow.x1, arrow.x2);
  assert.ok(arrow.y1 > sel.bottom && arrow.y2 < b.top);
});

test("insertPlacement: brak miejsca pod zaznaczeniem → przycisk nad nim, strzałka w górę; nie wychodzi poza okno", () => {
  const sel = { left: 760, top: 860, right: 900, bottom: 876 };
  const { button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.ok(b.top + button.height < sel.top);
  assert.ok(arrow.y1 < sel.top && arrow.y2 > b.top + button.height);
  const edge = insertPlacement({ left: 1420, top: 300, right: 1438, bottom: 316 }, { ...pane, left: 1300 }, button, view);
  assert.ok(edge.button.left + button.width <= view.width - 8);
});
