// Testy czystych funkcji układu (layout.js): podpisy pasków, statusy, położenie „Wstaw do” i strzałki.
import { test } from "node:test";
import assert from "node:assert/strict";
import { STATUS, avoidText, docsSummary, insertPlacement, positionText, progressText } from "../layout.js";

test("STATUS: każdy status ma tekst i ikonę (status nigdy samym kolorem)", () => {
  for (const key of ["selected", "queued", "pending", "ok", "unknown", "error"]) {
    assert.ok(STATUS[key].text.length > 0, key);
    assert.ok(STATUS[key].icon.length > 0, key);
  }
  assert.equal(STATUS.error.text, "Błąd");
  assert.equal(STATUS.unknown.text, "Nie rozpoznano");
});

test("docsSummary: liczba plików i to, co wymaga uwagi, z polską odmianą", () => {
  assert.deepEqual(docsSummary(["ok", "ok", "ok"]), { count: 3, attention: "", alert: false, progress: "" });
  assert.deepEqual(docsSummary(["ok", "error", "unknown", "ok", "ok"]),
    { count: 5, attention: "1 błąd, 1 nierozpoznany", alert: true, progress: "" });
  assert.equal(docsSummary(["error", "error", "ok"]).attention, "2 błędy");
  assert.equal(docsSummary(Array(5).fill("error")).attention, "5 błędów");
  assert.equal(docsSummary(["unknown", "unknown"]).attention, "2 nierozpoznane");
  assert.equal(docsSummary(["pending", "ok"]).attention, "1 z 2 gotowe");
  // plik po pliku: w kolejce i w trakcie liczą się jako niegotowe
  const run = docsSummary(["ok", "error", "pending", "queued", "queued"]);
  assert.equal(run.progress, "2 z 5 gotowe");
  assert.equal(run.attention, "2 z 5 gotowe, 1 błąd");
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

test("insertPlacement: miejsce po prawej → etykieta nad zaznaczeniem i po prawej, grot przy końcu zaznaczenia", () => {
  const sel = { left: 900, top: 400, right: 1050, bottom: 416 };
  const { side, button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.equal(side, "right");
  assert.ok(b.left > sel.right && b.left + button.width <= pane.right);
  assert.ok(b.top + button.height / 2 < sel.top, "etykieta wyżej niż zaznaczenie");
  // strzałka biegnie od lewej krawędzi etykiety ukośnie w dół do prawego końca zaznaczenia
  assert.ok(arrow.x1 < b.left + 1 && arrow.x1 > sel.right);
  assert.ok(arrow.x2 > sel.right && arrow.x2 < sel.right + 10);
  assert.equal(arrow.y2, 408);
  assert.ok(arrow.y1 < arrow.y2);
});

test("insertPlacement: zaznaczenie przy prawej krawędzi → etykieta po lewej, grot przy początku zaznaczenia", () => {
  const sel = { left: 1180, top: 400, right: 1420, bottom: 416 };
  const { side, button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.equal(side, "left");
  assert.ok(b.left >= pane.left && b.left + button.width < sel.left);
  assert.ok(arrow.x2 < sel.left && arrow.x2 > sel.left - 10);
  assert.ok(arrow.x1 > b.left + button.width - 1);
});

test("insertPlacement: wąski podgląd → etykieta pod zaznaczeniem, a przy dole okna nad nim", () => {
  const narrow = { left: 700, top: 150, right: 1000, bottom: 900 };
  const sel = { left: 720, top: 240, right: 980, bottom: 254 };
  const below = insertPlacement(sel, narrow, button, view);
  assert.equal(below.side, "below");
  assert.ok(below.button.top > sel.bottom);
  assert.equal(below.arrow.x1, below.arrow.x2);
  assert.ok(below.arrow.y2 > sel.bottom && below.arrow.y1 < below.button.top);
  const low = { left: 720, top: 860, right: 980, bottom: 874 };
  const above = insertPlacement(low, narrow, button, view);
  assert.equal(above.side, "above");
  assert.ok(above.button.top + button.height < low.top);
  assert.ok(above.arrow.y2 < low.top);
});


test("insertPlacement: brak miejsca pod zaznaczeniem → przycisk nad nim, strzałka w górę; nie wychodzi poza okno", () => {
  const sel = { left: 760, top: 860, right: 900, bottom: 876 };
  const { button: b, arrow } = insertPlacement(sel, pane, button, view);
  assert.ok(b.top + button.height < sel.top);
  assert.ok(arrow.y1 < sel.top && arrow.y2 > b.top + button.height);
  const edge = insertPlacement({ left: 1420, top: 300, right: 1438, bottom: 316 }, { ...pane, left: 1300 }, button, view);
  assert.ok(edge.button.left + button.width <= view.width - 8);
});

test("avoidText: etykieta schodzi z wiersza tekstu w prawo, a bez miejsca w górę; grot zostaje", () => {
  const sel = { left: 900, top: 400, right: 1050, bottom: 416 };
  const place = insertPlacement(sel, pane, button, view);
  const line = { left: 900, top: place.button.top + 4, right: 1180, bottom: place.button.top + 20 };
  const moved = avoidText(place, [line], button, { left: 708, right: 1432, top: 154 });
  assert.ok(moved.button.left >= line.right + 10);
  assert.equal(moved.arrow.x2, place.arrow.x2);
  assert.equal(moved.arrow.y2, place.arrow.y2);
  assert.equal(moved.arrow.x1, moved.button.left - 2);
  const wide = { left: 900, top: place.button.top + 4, right: 1420, bottom: place.button.top + 20 };
  const up = avoidText(place, [wide], button, { left: 708, right: 1432, top: 154 });
  assert.equal(up.button.left, place.button.left);
  assert.ok(up.button.top + button.height < wide.top);
  // nic nie zasłania → bez zmian
  assert.equal(avoidText(place, [], button, { left: 708, right: 1432, top: 154 }), place);
});
