// Testy kreatora „Dodaj typ dokumentu” (wizard.js): generowanie YAML i schematu oraz walidacja.
// Ostatni test sprawdza pliki prawdziwym backendem (load_configs), jeśli jest Python z PyYAML i jsonschema.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildPatterns,
  buildSchema,
  buildYaml,
  checkPythonRegex,
  defaultInstructions,
  fieldRule,
  filesOf,
  phraseToPattern,
  schemaText,
  slugify,
  supportsRule,
  toJsRegex,
  validate,
} from "../wizard.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

/** Kompletny, poprawny opis typu; testy nadpisują wybrane pola. */
const spec = (over = {}) => ({
  label: "Potwierdzenie odbioru",
  id: "potwierdzenie_odbioru",
  positive: "Potwierdzenie odbioru",
  negative: "",
  regex: false,
  minimum: 1,
  fields: [
    { key: "numer", label: "Numer potwierdzenia", type: "text", list: false, source: "Numer potwierdzenia:" },
    { key: "data_odbioru", label: "Data odbioru", type: "date", list: false, source: "Data odbioru" },
    { key: "oplata", label: "Kwota opłaty", type: "number", list: false, source: "Kwota opłaty" },
    { key: "nip_odbiorcy", label: "NIP odbiorcy", type: "digits", list: false, source: "NIP odbiorcy" },
    { key: "podpisane", label: "Czy podpisane", type: "bool", list: false, source: "Podpis" },
    { key: "zalaczniki", label: "Numery załączników", type: "text", list: true, source: "Załącznik" },
  ],
  hints: "",
  ...over,
});

/** Wartość grupy value po uruchomieniu reguły pola na tekście (przybliżenie regexu Pythona w JS). */
const valueOf = (field, text) => toJsRegex(fieldRule(field).pattern).exec(text)?.groups.value ?? null;

test("slugify: polskie znaki, odstępy i cyfry na początku", () => {
  assert.equal(slugify("Potwierdzenie odbioru"), "potwierdzenie_odbioru");
  assert.equal(slugify("Żółć gęślą jaźń — Umowa!"), "zolc_gesla_jazn_umowa");
  assert.equal(slugify("  2026 Faktura VAT  "), "faktura_vat");
  assert.equal(slugify(""), "");
});

test("phraseToPattern: znaki specjalne regexu i dowolne odstępy", () => {
  assert.equal(phraseToPattern("Potwierdzenie   odbioru"), String.raw`(?i)Potwierdzenie\s+odbioru`);
  assert.equal(phraseToPattern("Nr (faktury): [A-Z]? 1.5"), String.raw`(?i)Nr\s+\(faktury\):\s+\[A-Z\]\?\s+1\.5`);
  assert.equal(phraseToPattern("   "), "");
});

test("buildPatterns: jedna fraza w wierszu, bez powtórzeń; tryb regex bez zmian", () => {
  assert.deepEqual(buildPatterns("FAKTURA VAT\n\nfaktura  vat\nFAKTURA VAT ", false), [String.raw`(?i)FAKTURA\s+VAT`, String.raw`(?i)faktura\s+vat`]);
  assert.deepEqual(buildPatterns(String.raw`(?im)^\s*wyrok\b` + "\r\n" + String.raw`(?im)^\s*wyrok\b`, true), [String.raw`(?im)^\s*wyrok\b`]);
});

test("buildSchema: typy pól, null dla pustych, listy i wymagane klucze", () => {
  const schema = buildSchema(spec());
  assert.equal(schema.type, "object");
  assert.equal(schema.additionalProperties, false);
  assert.deepEqual(schema.required, ["numer", "data_odbioru", "oplata", "nip_odbiorcy", "podpisane", "zalaczniki"]);
  assert.deepEqual(schema.properties.numer, { type: ["string", "null"], description: "Numer potwierdzenia" });
  assert.deepEqual(schema.properties.data_odbioru, { type: ["string", "null"], format: "date", description: "Data odbioru" });
  assert.deepEqual(schema.properties.oplata, { type: ["number", "null"], description: "Kwota opłaty" });
  assert.deepEqual(schema.properties.nip_odbiorcy, { type: ["string", "null"], pattern: "^[0-9]+$", description: "NIP odbiorcy" });
  assert.deepEqual(schema.properties.podpisane, { type: ["boolean", "null"], description: "Czy podpisane" });
  assert.deepEqual(schema.properties.zalaczniki, { type: "array", description: "Numery załączników", items: { type: "string" } });
});

test("schemaText: poprawny JSON, krótkie listy w jednym wierszu", () => {
  const text = schemaText(spec());
  assert.deepEqual(JSON.parse(text), buildSchema(spec()));
  assert.match(text, /"type": \["string", "null"\]/);
  assert.ok(text.endsWith("}\n"));
});

test("fieldRule: normalizator zgodny z typem, brak reguły dla tak/nie, list i pustej etykiety", () => {
  const [numer, data, oplata, nip, podpisane, zalaczniki] = spec().fields;
  assert.equal(fieldRule(numer).normalize, "text");
  assert.equal(fieldRule(data).normalize, "iso_date");
  assert.equal(fieldRule(oplata).normalize, "amount");
  assert.equal(fieldRule(nip).normalize, "digits");
  assert.equal(fieldRule(podpisane), null);
  assert.equal(fieldRule(zalaczniki), null);
  assert.equal(fieldRule({ ...numer, source: "  " }), null);
  assert.equal(supportsRule({ type: "bool", list: false }), false);
  assert.equal(supportsRule({ type: "digits", list: true }), false);
  for (const field of [numer, data, oplata, nip]) assert.match(fieldRule(field).pattern, /\(\?P<value>/);
});

test("fieldRule: wartość po etykiecie w tym samym lub następnym wierszu", () => {
  const [numer, data, oplata, nip] = spec().fields;
  assert.equal(valueOf(numer, "POTWIERDZENIE\nnumer potwierdzenia:  PO/15/2026  \nDalej"), "PO/15/2026");
  assert.equal(valueOf(data, "Data odbioru:\n15.11.2026 r."), "15.11.2026");
  assert.equal(valueOf(data, "DATA ODBIORU 2026-11-15"), "2026-11-15");
  assert.equal(valueOf(oplata, "Kwota opłaty: 1 234,56 zł"), "1 234,56");
  assert.equal(valueOf(nip, "NIP odbiorcy: 012-345-67-89 REGON 1"), "012-345-67-89");
  assert.equal(valueOf(numer, "Inny dokument"), null);
});

test("fieldRule: własny regex z grupą (?P<value>) przechodzi bez zmian", () => {
  const raw = String.raw`(?i)sygn\.\s*akt:?\s*(?P<value>KIO\s+\d+/\d{2})`;
  const rule = fieldRule({ key: "sygnatura", label: "Sygnatura", type: "text", list: false, source: raw });
  assert.deepEqual(rule, { pattern: raw, normalize: "text" });
  assert.equal(toJsRegex(rule.pattern).exec("Sygn. akt: KIO 1234/26").groups.value, "KIO 1234/26");
});

test("buildYaml: struktura, cudzysłowy i wieloliniowe wskazówki", () => {
  const yaml = buildYaml(spec({
    label: "Pismo 'test' \"cytat\"",
    negative: "Wezwanie do odbioru",
    minimum: 1,
    hints: "Wiersz 1 z 'apostrofem'\r\nWiersz 2 z \\ i \"cudzysłowem\"",
  }));
  const lines = yaml.split("\n");
  assert.equal(lines[2], "id: potwierdzenie_odbioru");
  assert.equal(lines[3], "schema: potwierdzenie_odbioru.schema.json");
  assert.ok(lines.includes("  positive_patterns:"));
  assert.ok(lines.includes(String.raw`    - '(?i)Potwierdzenie\s+odbioru'`));
  assert.ok(lines.includes("  negative_patterns:"));
  assert.ok(lines.includes("  minimum_matches: 1"));
  assert.ok(lines.includes(`  label: "Pismo 'test' \\"cytat\\""`));
  assert.ok(lines.includes(`  llm_instructions: "Wiersz 1 z 'apostrofem'\\nWiersz 2 z \\\\ i \\"cudzysłowem\\""`));
  // reguły tylko dla pól, które je obsługują, w kolejności formularza
  const fieldsAt = lines.indexOf("fields:");
  assert.ok(fieldsAt > 0 && fieldsAt < lines.indexOf("options:"));
  const keys = lines.slice(fieldsAt + 1, lines.indexOf("options:")).filter((l) => /^  \S/.test(l));
  assert.deepEqual(keys, ["  numer:", "  data_odbioru:", "  oplata:", "  nip_odbiorcy:"]);
  assert.ok(yaml.endsWith("\n"));
});

test("buildYaml: apostrof w regexie podwojony, klucze yes/on w cudzysłowie, bez pustych sekcji", () => {
  const yaml = buildYaml(spec({
    positive: "Oświadczenie o'Neill",
    fields: [{ key: "on", label: "Pole on", type: "text", list: false, source: "On:" }],
  }));
  assert.ok(yaml.includes(String.raw`    - '(?i)Oświadczenie\s+o''Neill'`));
  assert.ok(yaml.includes("\n  'on':\n"));
  assert.ok(!yaml.includes("negative_patterns"));
  assert.ok(!buildYaml(spec({ fields: [{ key: "a", label: "A", type: "bool", list: false }] })).includes("fields:"));
});

test("defaultInstructions: frazy rozpoznawania i reguły tylko dla użytych typów", () => {
  const text = defaultInstructions(spec({ fields: [{ key: "d", label: "D", type: "date", list: false }] }));
  assert.match(text, /„Potwierdzenie odbioru”/);
  assert.match(text, /RRRR-MM-DD/);
  assert.doesNotMatch(text, /Liczby|Identyfikatory/);
  assert.match(buildYaml(spec({ hints: "Własne wskazówki." })), /llm_instructions: "Własne wskazówki\."/);
});

test("validate: poprawny opis nie ma błędów", () => {
  assert.deepEqual(validate(spec(), ["odwolanie"]), { errors: [], warnings: [] });
});

test("validate: identyfikator jak w backendzie (format, unknown, istniejące typy)", () => {
  const idError = (id, existing = []) => validate(spec({ id }), existing).errors.find((e) => e.target === "id")?.msg;
  assert.match(idError(""), /Wpisz identyfikator/);
  assert.match(idError("Faktura"), /małe litery/);
  assert.match(idError("1faktura"), /na początku litera/);
  assert.match(idError("faktura-vat"), /małe litery/);
  assert.match(idError("unknown"), /zastrzeżony/);
  assert.match(idError("przelew"), /już istnieje/);
  assert.match(idError("wyrok_kio", ["wyrok_kio"]), /już istnieje/);
  assert.equal(idError("faktura_vat_2"), undefined);
});

test("validate: frazy, próg i pola", () => {
  const targets = (over) => validate(spec(over)).errors.map((e) => e.target);
  assert.deepEqual(targets({ label: " " }), ["label"]);
  assert.deepEqual(targets({ positive: "\n \n" }), ["positive"]);
  assert.deepEqual(targets({ positive: "A\nB", minimum: 3 }), ["minimum"]);
  assert.deepEqual(targets({ positive: "A\na", minimum: 2 }), []);   // inne wielkości liter to dwa wzorce
  assert.deepEqual(targets({ positive: "A\nA", minimum: 2 }), ["minimum"]);
  assert.deepEqual(targets({ minimum: 0 }), ["minimum"]);
  assert.deepEqual(targets({ fields: [] }), ["fields"]);
  assert.deepEqual(targets({ fields: [
    { key: "", label: "A", type: "text" },
    { key: "zły klucz", label: "B", type: "text" },
    { key: "x", label: "C", type: "text" },
    { key: "x", label: " ", type: "text" },
  ] }), ["key:0", "key:1", "key:3", "flabel:3"]);
});

test("validate: niepoprawny regex daje ostrzeżenie, a nie błąd", () => {
  const { errors, warnings } = validate(spec({ regex: true, positive: "(?i)abc(", minimum: 1 }));
  assert.deepEqual(errors, []);
  assert.equal(warnings[0].target, "positive");
  const field = { key: "n", label: "N", type: "text", list: false, source: "(?P<value>[a-z)" };
  assert.equal(validate(spec({ fields: [field] })).warnings[0].target, "source:0");
  assert.equal(checkPythonRegex(String.raw`(?im)^\s*(?P<nr>\d+)(?P=nr)\Z`), null);
});

test("filesOf: ścieżki zgodne z układem repozytorium", () => {
  assert.deepEqual(filesOf(spec()).map((f) => f.name), [
    "configs/documents/potwierdzenie_odbioru.yaml",
    "schemas/potwierdzenie_odbioru.schema.json",
  ]);
});

/** Python z PyYAML i jsonschema: $PYTHON, .venv repozytorium albo python z PATH. */
function findPython() {
  const candidates = [process.env.PYTHON, join(REPO, ".venv", "Scripts", "python.exe"), join(REPO, ".venv", "bin", "python"), "python3", "python"];
  return candidates.filter(Boolean).find((cmd) => spawnSync(cmd, ["-c", "import yaml, jsonschema"], { stdio: "ignore" }).status === 0);
}

const BACKEND_CHECK = `
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from jsonschema import Draft202012Validator
from kio_extract.classifier import classify
from kio_extract.contracts import ExtractedDocument, PageText
from kio_extract.extraction_engine import resolve_extractor
from kio_extract.schema_registry import load_configs
configs = load_configs(Path(sys.argv[2]), Path(sys.argv[3]))
doc = ExtractedDocument(Path("test.pdf"), (PageText(1, sys.argv[4]),))
result = classify(doc, tuple(configs.values()))
config = configs.get(result.doc_type)
data = resolve_extractor(config)(doc, config).data if config else None
validator = Draft202012Validator(config.schema, format_checker=Draft202012Validator.FORMAT_CHECKER) if config else None
errors = [e.message for e in validator.iter_errors(data)] if config else []
print(json.dumps({"types": sorted(configs), "doc_type": result.doc_type, "data": data, "errors": errors}, ensure_ascii=False))
`;

const python = findPython();

test("backend: load_configs przyjmuje wygenerowane pliki, a tryb bez modelu je wypełnia", { skip: python ? false : "brak Pythona z PyYAML i jsonschema" }, () => {
  const dir = mkdtempSync(join(tmpdir(), "kreator-"));
  try {
    const configs = join(dir, "configs", "documents");
    const schemas = join(dir, "schemas");
    mkdirSync(configs, { recursive: true });
    mkdirSync(schemas, { recursive: true });
    // istniejące typy też muszą się wczytać razem z nowym
    for (const name of readdirSync(join(REPO, "configs", "documents"))) cpSync(join(REPO, "configs", "documents", name), join(configs, name));
    for (const name of readdirSync(join(REPO, "schemas"))) cpSync(join(REPO, "schemas", name), join(schemas, name));
    for (const file of filesOf(spec({ hints: "Wiersz 1\nWiersz 2 z 'apostrofem'" }))) writeFileSync(join(dir, file.name), file.text);

    const text = "POTWIERDZENIE ODBIORU\nNumer potwierdzenia: PO/15/2026\nData odbioru:\n15.11.2026\nKwota opłaty: 1 234,56 zł\nNIP odbiorcy: 012-345-67-89\n";
    const run = spawnSync(python, ["-c", BACKEND_CHECK, join(REPO, "src"), configs, schemas, text], {
      encoding: "utf8",
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    assert.equal(run.status, 0, run.stderr);
    const out = JSON.parse(run.stdout);
    assert.ok(out.types.includes("potwierdzenie_odbioru") && out.types.includes("odwolanie"));
    assert.equal(out.doc_type, "potwierdzenie_odbioru");
    assert.deepEqual(out.data, {
      numer: "PO/15/2026",
      data_odbioru: "2026-11-15",
      oplata: 1234.56,
      nip_odbiorcy: "0123456789",
      podpisane: null,
      zalaczniki: [],
    });
    assert.deepEqual(out.errors, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
