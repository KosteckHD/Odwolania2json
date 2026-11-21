// Testy sum kontrolnych (parse.js): NIP, REGON 9 i 14, PESEL, rachunek NRB (IBAN PL mod 97).
import { test } from "node:test";
import assert from "node:assert/strict";
import { accountValid, checksumValid, nipValid, peselValid, regonValid } from "../parse.js";

test("NIP: wagi 6,5,7,2,3,4,5,6,7", () => {
  assert.equal(nipValid("1234563218"), true);
  assert.equal(nipValid("5540240549"), true);
  assert.equal(nipValid("1234563217"), false);
  assert.equal(nipValid("123456321"), null);       // za krótki: nie oceniamy sumy
  assert.equal(nipValid("12345a3218"), null);
});

test("NIP z resztą 10 jest zawsze błędny", () => {
  // 0000000060: suma = 6·6 = 36 → … ; szukamy numeru z resztą 10
  const base = "123456789";
  const r = [6, 5, 7, 2, 3, 4, 5, 6, 7].reduce((s, w, i) => s + w * Number(base[i]), 0) % 11;
  assert.equal(r, 10);
  for (let last = 0; last <= 9; last++) assert.equal(nipValid(`${base}${last}`), false);
});

test("REGON 9 i 14 cyfr (reszta 10 liczy się jako 0)", () => {
  assert.equal(regonValid("123456785"), true);
  assert.equal(regonValid("000279077"), true);
  assert.equal(regonValid("123456786"), false);
  assert.equal(regonValid("12345678512347"), true);
  assert.equal(regonValid("12345678500002"), true);
  assert.equal(regonValid("12345678512348"), false);
  assert.equal(regonValid("1234567851"), null);
});

test("PESEL: wagi 1,3,7,9,…, cyfra kontrolna (10 − suma mod 10) mod 10", () => {
  assert.equal(peselValid("44051401359"), true);
  assert.equal(peselValid("44051401358"), false);
  assert.equal(peselValid("4405140135"), null);
});

test("rachunek NRB jako IBAN PL: mod 97 = 1", () => {
  assert.equal(accountValid("61109010140000071219812874"), true);
  assert.equal(accountValid("60101010100081362231000000"), true);
  assert.equal(accountValid("61 1090 1014 0000 0712 1981 2874"), true);
  assert.equal(accountValid("61109010140000071219812875"), false);
  assert.equal(accountValid("508020546000005888744244"), null);   // 24 cyfry: najpierw długość
});

test("checksumValid po kluczu rubryki: KRS i inne pola bez sumy → null", () => {
  assert.equal(checksumValid("Odwolujacy.0.nip", "5540240549"), true);
  assert.equal(checksumValid("mocodawca.0.data.nip", "8361772283"), true);
  assert.equal(checksumValid("Zamawiajacy.0.regon", "000279076"), false);
  assert.equal(checksumValid("pelnomocnicy.0.pesel", 44051401359), true);
  // PESEL zapisany jako liczba gubi zero z przodu (urodzeni po 2000): uzupełniamy do 11 cyfr
  assert.equal(checksumValid("pelnomocnicy.0.pesel", 2070803628), true);
  assert.equal(checksumValid("przelew_bankowy.na_rachunek", "61109010140000071219812874"), true);
  assert.equal(checksumValid("Odwolujacy.0.krs", "0000054588"), null);
  assert.equal(checksumValid("Odwolujacy.0.nip", null), null);
});
