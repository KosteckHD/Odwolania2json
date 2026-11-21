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

/* ---------- formularz ze schematu (schemaToSpec) ---------- */
import { fieldFromSchema, prettyKey, schemaToSpec } from "../fields.js";
import { buildSchema } from "../wizard.js";

// to samo co EXAMPLE w kreatorze („Wypełnij przykładem”)
const WIZARD_EXAMPLE = {
  label: "Potwierdzenie odbioru",
  fields: [
    { key: "numer", label: "Numer potwierdzenia", type: "text", list: false },
    { key: "data_odbioru", label: "Data odbioru", type: "date", list: false },
    { key: "podpisane", label: "Czy dokument jest podpisany", type: "bool", list: false },
  ],
};

test("prettyKey: klucz na „Ładny tekst”", () => {
  assert.equal(prettyKey("data_odbioru"), "Data odbioru");
  assert.equal(prettyKey("numerUmowy"), "Numer umowy");
  assert.equal(prettyKey("kwota"), "Kwota");
});

test("schemaToSpec na schemacie z kreatora: etykiety z description, data w kratkach, krzyżyk tak/nie", () => {
  const spec = schemaToSpec(buildSchema(WIZARD_EXAMPLE), "Potwierdzenie odbioru");
  assert.equal(spec.label, "Potwierdzenie odbioru");
  assert.equal(spec.groups.length, 1);
  const [group] = spec.groups;
  assert.equal(group.root, true);
  assert.equal(group.path, "");
  assert.deepEqual(group.fields.map((f) => [f.key, f.label, f.kind]), [
    ["numer", "Numer potwierdzenia", "text"],
    ["data_odbioru", "Data odbioru", "date"],
    ["podpisane", "Czy dokument jest podpisany", "bool"],
  ]);
});

test("fieldFromSchema: liczby, kwoty, cyfry z wzorca, listy prostych wartości", () => {
  assert.equal(fieldFromSchema("kwota", { type: ["number", "null"] }).kind, "amount");
  assert.deepEqual(fieldFromSchema("liczba_stron", { type: "integer" }), { key: "liczba_stron", label: "Liczba stron", kind: "number", integer: true });
  assert.deepEqual(fieldFromSchema("nr", { type: ["string", "null"], pattern: "^[0-9]+$", description: "Numer" }), { key: "nr", label: "Numer", kind: "digits" });
  assert.deepEqual(fieldFromSchema("regon", { type: "string", pattern: "^[0-9]{9}$" }).lengths, [9]);
  assert.equal(fieldFromSchema("x", { type: "string", pattern: "^[A-Z]+$" }).kind, "text");
  assert.deepEqual(fieldFromSchema("tagi", { type: "array", items: { type: "string" } }), { key: "tagi", label: "Tagi", kind: "lines", wide: true, numeric: false });
  assert.equal(fieldFromSchema("lista", { type: "array", items: { type: "object", properties: {} } }), null);
});

test("schemaToSpec: zagnieżdżony obiekt to osobna grupa, tablica obiektów to grupa listy", () => {
  const schema = {
    type: "object",
    properties: {
      numer: { type: "string" },
      nadawca: {
        type: "object", description: "Nadawca pisma",
        properties: { nazwa: { type: "string" }, adres: { type: "object", properties: { miasto: { type: "string", description: "Miasto" } } } },
      },
      osoby: {
        type: "array", description: "Osoby",
        items: { type: "object", properties: { imie_nazwisko: { type: "string" }, pesel: { type: "string", pattern: "^[0-9]{11}$" } } },
      },
    },
  };
  const spec = schemaToSpec(schema, "Pismo");
  assert.deepEqual(spec.groups.map((g) => [g.title, g.path, Boolean(g.list), Boolean(g.root)]), [
    ["Dane dokumentu", "", false, true],
    ["Nadawca pisma", "nadawca", false, false],
    ["Osoby", "osoby", true, false],
  ]);
  assert.deepEqual(spec.groups[1].fields.map((f) => [f.key, f.label]), [["nazwa", "Nazwa"], ["adres.miasto", "Miasto"]]);
  assert.deepEqual(spec.groups[2].fields.map((f) => [f.key, f.kind]), [["imie_nazwisko", "text"], ["pesel", "digits"]]);
  assert.ok(spec.groups[2].item);
});
