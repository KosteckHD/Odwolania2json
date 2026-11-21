// Testy opisu rubryk (fields.js): pusta pozycja listy.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DOC_TYPES, emptyListItem } from "../fields.js";

const groupOf = (type, path) => DOC_TYPES[type].groups.find((g) => g.path === path);

test("emptyListItem: struktura z rubryk, gdy brak wzoru (zagnieżdżone klucze, names jako [])", () => {
  const odw = groupOf("odwolanie", "Odwolujacy");
  assert.deepEqual(emptyListItem(odw.fields), {
    nazwa: null, krs: null, nip: null, regon: null, "przez-pelnomocnika": null,
    pelnomocnik: { imie_nazwisko: null, nazwa: null, mail: null },
  });
  const moc = groupOf("pelnomocnictwo", "mocodawca");
  assert.deepEqual(emptyListItem(moc.fields), {
    data: { nazwa: null, typ: null, imie_nazwisko: null, krs: null, nip: null }, podpisujacy: [],
  });
});

test("emptyListItem: wzór od modelu zachowuje klucze spoza rubryk, wartości wyczyszczone", () => {
  const pel = groupOf("pelnomocnictwo", "pelnomocnicy");
  const template = { imie_nazwisko: "Jan Kowalski i Anna Nowak", pesel: 85120133547, adres: { miasto: "Gdańsk" }, role: ["radca"] };
  assert.deepEqual(emptyListItem(pel.fields, template), { imie_nazwisko: null, pesel: null, adres: { miasto: null }, role: [] });
  // wzór nie jest zmieniany
  assert.equal(template.imie_nazwisko, "Jan Kowalski i Anna Nowak");
});

test("grupy list mają nazwę pozycji do przycisku „+ Dodaj …”", () => {
  for (const type of Object.values(DOC_TYPES)) {
    for (const group of type.groups.filter((g) => g.list)) assert.ok(group.item, group.title);
  }
});
