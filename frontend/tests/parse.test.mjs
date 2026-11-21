// Testy czystych funkcji z parse.js (wstawianie tekstu z PDF-u do rubryk).
import { test } from "node:test";
import assert from "node:assert/strict";
import { expectedDigits, pickAmount, pickCode, pickDate, pickDigits, pickText } from "../parse.js";

test("expectedDigits: długości identyfikatorów po nazwie klucza", () => {
  assert.deepEqual(expectedDigits("krs"), [10]);
  assert.deepEqual(expectedDigits("Odwolujacy.nip"), [10]);
  assert.deepEqual(expectedDigits("regon"), [9, 14]);
  assert.deepEqual(expectedDigits("pelnomocnicy.pesel"), [11]);
  assert.deepEqual(expectedDigits("z_rachunku"), [26]);
  assert.deepEqual(expectedDigits("nazwa"), []);
});

test("pickDigits: numer KRS ze spacjami", () => {
  assert.equal(pickDigits("KRS: 0000 054 588", [10]), "0000054588");
});

test("pickDigits: NIP z myślnikami", () => {
  assert.equal(pickDigits("NIP: 526-025-09-95", [10]), "5260250995");
});

test("pickDigits: wybiera liczbę o oczekiwanej długości spośród kilku", () => {
  const text = "KRS 0000054588, NIP 5260250995, REGON 012345678";
  assert.equal(pickDigits(text, [9, 14]), "012345678");
  assert.equal(pickDigits("ul. Prosta 12, PESEL: 85120133547", [11]), "85120133547");
});

test("pickDigits: numer rachunku rozbity na grupy", () => {
  assert.equal(
    pickDigits("PL 60 1010 1010 0081 3622 3100 0000", [26]),
    "60101010100081362231000000",
  );
});

test("pickDigits: bez oczekiwanej długości bierze najdłuższą liczbę; brak cyfr → pusty tekst", () => {
  assert.equal(pickDigits("nr 12, sygn. 345678"), "345678");
  assert.equal(pickDigits("brak numeru", [10]), "");
});

test("pickDate: DD.MM.RRRR", () => {
  assert.equal(pickDate("Pruszków, dnia 13.10.2025"), "2025-10-13");
  assert.equal(pickDate("1.2.2025"), "2025-02-01");
});

test("pickDate: RRRR-MM-DD", () => {
  assert.equal(pickDate("data operacji: 2025-10-09"), "2025-10-09");
});

test("pickDate: miesiąc słownie", () => {
  assert.equal(pickDate("Warszawa, 14 października 2025 r."), "2025-10-14");
  assert.equal(pickDate("1 Maja 2024"), "2024-05-01");
});

test("pickDate: błędna albo brakująca data → null", () => {
  assert.equal(pickDate("32.13.2025"), null);
  assert.equal(pickDate("2025-00-10"), null);
  assert.equal(pickDate("14 smarca 2025"), null);
  assert.equal(pickDate("brak daty"), null);
});

test("pickAmount: format polski ze spacjami i z kropkami", () => {
  assert.equal(pickAmount("10 000,00 zł"), 10000);
  assert.equal(pickAmount("10.000,00 PLN"), 10000);
  assert.equal(pickAmount("Kwota: 1 234,56 zł"), 1234.56);
  assert.equal(pickAmount("15000"), 15000);
});

test("pickAmount: brak liczby → null", () => {
  assert.equal(pickAmount("dziesięć tysięcy"), null);
});

test("pickCode: kod powodu 1–12", () => {
  assert.equal(pickCode("Powód: 4"), 4);
  assert.equal(pickCode("12"), 12);
  assert.equal(pickCode("13"), null);
  assert.equal(pickCode("0"), null);
  assert.equal(pickCode("brak"), null);
});

test("pickText: usuwa etykietę i cudzysłowy, scala białe znaki", () => {
  assert.equal(pickText("Odwołujący: STRABAG Sp. z o.o."), "STRABAG Sp. z o.o.");
  assert.equal(pickText("  Filharmonia\n Pomorska  "), "Filharmonia Pomorska");
  assert.equal(pickText("Tytuł: „Budowa drogi”"), "Budowa drogi");
});

test("pickText: zostawia tekst, gdy dwukropek nie jest etykietą", () => {
  assert.equal(pickText("Odwołujący:"), "Odwołujący:");
  const long = "Wykonanie robót budowlanych w ramach zadania nr 1: przebudowa";
  assert.equal(pickText(long), long);
});
