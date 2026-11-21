// Kreator „Dodaj typ dokumentu” (widok „Typy dokumentów”, sekcja dla administratora).
// Z formularza powstają dwa pliki w formacie backendu (docs/ADD_DOCUMENT_TYPE.md):
//   configs/documents/<typ>.yaml   – rozpoznawanie i wskazówki dla modelu
//   schemas/<typ>.schema.json      – pola danych w JSON-ie
// Wszystko dzieje się w przeglądarce: panel niczego nie wysyła, tylko daje pliki do pobrania.

import { zipStore } from "./zip.js";

/* ---------- generowanie plików (bez DOM, do testów w Node) ---------- */

export const FIELD_TYPES = {
  text:   { label: "Tekst", schema: { type: "string" } },
  number: { label: "Liczba", schema: { type: "number" } },
  date:   { label: "Data", schema: { type: "string", format: "date" } },
  digits: { label: "Identyfikator cyfrowy", schema: { type: "string", pattern: "^[0-9]+$" } },
  bool:   { label: "Tak / nie", schema: { type: "boolean" } },
};

// Te same reguły co w backendzie (schema_registry.load_configs).
const ID_RE = /^[a-z][a-z0-9_]*$/;
const KEY_RE = /^[A-Za-z][A-Za-z0-9_]*$/;
const KNOWN_IDS = ["odwolanie", "pelnomocnictwo", "przelew"];
const SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema";
// Znaki, których YAML nie przyjmie albo które łamią wiersz.
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u2028\u2029\uFEFF\uFFFE\uFFFF]/g;
const PL = { ą: "a", ć: "c", ę: "e", ł: "l", ń: "n", ó: "o", ś: "s", ź: "z", ż: "z" };

const clean = (text) => String(text ?? "").replace(/\r\n?/g, "\n").replace(CONTROL, " ");
const oneLine = (text) => clean(text).replace(/\s+/g, " ").trim();
const lines = (text) => clean(text).split("\n").map((l) => l.trim()).filter(Boolean);

/** „Potwierdzenie odbioru” → „potwierdzenie_odbioru”. */
export function slugify(text) {
  return oneLine(text).toLowerCase()
    .replace(/[ąćęłńóśźż]/g, (c) => PL[c])
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^[0-9_]+|_+$/g, "");
}

/** Fraza z dokumentu → regex Pythona bez rozróżniania wielkości liter, odporny na odstępy. */
export function phraseToPattern(phrase) {
  const words = oneLine(phrase).split(" ").filter(Boolean);
  if (!words.length) return "";
  return `(?i)${words.map((w) => w.replace(/[\\.^$*+?{}[\]|()]/g, "\\$&")).join("\\s+")}`;
}

/** Przybliżone sprawdzenie regexu Pythona silnikiem przeglądarki. Zwraca opis błędu albo null. */
export function checkPythonRegex(source) {
  let flags = "";
  const body = source
    .replace(/^\(\?([aiLmsux]+)\)/, (_, f) => { flags = [...new Set(f.replace(/[aLux]/g, ""))].join(""); return ""; })
    .replace(/\(\?P</g, "(?<").replace(/\(\?P=(\w+)\)/g, "\\k<$1>")
    .replace(/\\A/g, "^").replace(/\\Z/g, "$");
  try { new RegExp(body, flags); return null; } catch (e) { return e.message; }
}

export function buildPatterns(text, regex) {
  const out = lines(text).map((l) => (regex ? l : phraseToPattern(l))).filter(Boolean);
  return [...new Set(out)];   // backend odrzuca powtórzone wzorce
}

function propertySchema(field) {
  const { schema } = FIELD_TYPES[field.type] ?? FIELD_TYPES.text;
  const { type, ...rest } = schema;
  const label = oneLine(field.label);
  const description = label ? { description: label } : {};
  if (field.list) return { type: "array", ...description, items: { type, ...rest } };
  return { type: [type, "null"], ...rest, ...description };
}

export function buildSchema(spec) {
  const properties = {};
  for (const field of spec.fields) if (field.key) properties[field.key] = propertySchema(field);
  return {
    $schema: SCHEMA_DRAFT,
    type: "object",
    additionalProperties: false,
    required: Object.keys(properties),
    properties,
  };
}

export function defaultInstructions(spec) {
  const name = oneLine(spec.label) || "nowy typ";
  const parts = [`Dokument typu „${name}”.`];
  if (!spec.regex) {
    const phrases = lines(spec.positive).map(oneLine);
    if (phrases.length) parts.push(`Rozpoznasz go po frazach: ${phrases.map((p) => `„${p}”`).join(", ")}.`);
  }
  parts.push("Wypełnij pola zgodnie z ich opisami w schemacie.");
  const types = new Set(spec.fields.map((f) => f.type));
  if (types.has("date")) parts.push("Daty zapisuj jako RRRR-MM-DD.");
  if (types.has("number")) parts.push("Liczby podawaj bez jednostek i separatorów tysięcy, z kropką dziesiętną.");
  if (types.has("digits")) parts.push("Identyfikatory cyfrowe zapisuj samymi cyframi, z zerami na początku.");
  parts.push("Jeśli wartości nie ma w dokumencie, wpisz null, a listę zostaw pustą.");
  return parts.join(" ");
}

export const instructionsOf = (spec) => clean(spec.hints).trim() || defaultInstructions(spec);

const yamlSingle = (s) => `'${s.replace(/'/g, "''")}'`;
const yamlDouble = (s) => JSON.stringify(s);   // JSON jest poprawnym skalarem YAML w cudzysłowie

export function buildYaml(spec) {
  const id = spec.id || "nowy_typ";
  const label = oneLine(spec.label);
  const positive = buildPatterns(spec.positive, spec.regex);
  const negative = buildPatterns(spec.negative, spec.regex);
  const out = [
    `# Typ dokumentu: ${label || id}`,
    "# Przygotowano w kreatorze panelu Odwołania2JSON.",
    `id: ${id}`,
    `schema: ${id}.schema.json`,
    "classification:",
    "  positive_patterns:",
    ...(positive.length ? positive.map((p) => `    - ${yamlSingle(p)}`) : ["    []"]),
  ];
  if (negative.length) out.push("  negative_patterns:", ...negative.map((p) => `    - ${yamlSingle(p)}`));
  out.push(`  minimum_matches: ${spec.minimum}`, "options:");
  if (label) out.push(`  label: ${yamlDouble(label)}`);
  out.push(`  llm_instructions: ${yamlDouble(instructionsOf(spec))}`);
  return `${out.join("\n")}\n`;
}

// Krótkie listy tekstów w jednym wierszu: "type": ["string", "null"] zamiast pięciu linii.
const compactArrays = (json) => json.replace(/\[\n\s+((?:"[^"\n]*",\n\s+)*"[^"\n]*")\n\s+\]/g, (all, items) => {
  const one = `[${items.split(/,\n\s+/).join(", ")}]`;
  return one.length <= 60 ? one : all;
});

export const schemaText = (spec) => `${compactArrays(JSON.stringify(buildSchema(spec), null, 2))}\n`;

export function filesOf(spec) {
  return [
    { name: `configs/documents/${spec.id}.yaml`, text: buildYaml(spec) },
    { name: `schemas/${spec.id}.schema.json`, text: schemaText(spec) },
  ];
}

/**
 * Błędy blokują pobranie, ostrzeżenia nie. `target` wskazuje pole formularza:
 * "label", "id", "positive", "negative", "minimum", "fields", "key:<n>", "flabel:<n>".
 */
export function validate(spec, existingIds = []) {
  const errors = [];
  const warnings = [];
  const err = (target, msg) => errors.push({ target, msg });

  if (!oneLine(spec.label)) err("label", "Wpisz nazwę wyświetlaną.");
  if (!spec.id) err("id", "Wpisz identyfikator typu.");
  else if (!ID_RE.test(spec.id)) err("id", "Identyfikator: małe litery bez polskich znaków, cyfry i podkreślenie, na początku litera.");
  else if (spec.id === "unknown") err("id", "Identyfikator „unknown” jest zastrzeżony dla nierozpoznanych dokumentów.");
  else if (new Set([...KNOWN_IDS, ...existingIds]).has(spec.id)) err("id", `Typ „${spec.id}” już istnieje. Wybierz inny identyfikator.`);

  const positive = buildPatterns(spec.positive, spec.regex);
  if (!positive.length) err("positive", "Podaj co najmniej jedną frazę rozpoznawania.");
  if (!Number.isInteger(spec.minimum) || spec.minimum < 1) err("minimum", "Próg musi być liczbą całkowitą od 1.");
  else if (positive.length && spec.minimum > positive.length) {
    err("minimum", `Próg (${spec.minimum}) nie może być większy niż liczba różnych fraz (${positive.length}).`);
  }
  if (spec.regex) {
    for (const [target, text] of [["positive", spec.positive], ["negative", spec.negative]]) {
      for (const pattern of buildPatterns(text, true)) {
        const problem = checkPythonRegex(pattern);
        if (problem) warnings.push({ target, msg: `Wzorzec ${pattern} wygląda na niepoprawny (${problem}). Backend sprawdzi go przy starcie.` });
      }
    }
  }

  if (!spec.fields.length) err("fields", "Dodaj co najmniej jedno pole danych.");
  const seen = new Set();
  spec.fields.forEach((field, i) => {
    const no = i + 1;
    if (!field.key) err(`key:${i}`, `Pole ${no}: wpisz klucz w JSON.`);
    else if (!KEY_RE.test(field.key)) err(`key:${i}`, `Pole ${no}: klucz może mieć litery bez polskich znaków, cyfry i podkreślenie, na początku litera.`);
    else if (seen.has(field.key)) err(`key:${i}`, `Pole ${no}: klucz „${field.key}” już jest na liście.`);
    seen.add(field.key);
    if (!oneLine(field.label)) err(`flabel:${i}`, `Pole ${no}: wpisz etykietę po polsku (podpowiada modelowi, co wpisać).`);
  });
  return { errors, warnings };
}

/* ---------- formularz ---------- */

const EXAMPLE = {
  label: "Potwierdzenie odbioru",
  positive: "Potwierdzenie odbioru",
  negative: "",
  regex: false,
  minimum: 1,
  fields: [
    { key: "numer", label: "Numer potwierdzenia", type: "text", list: false },
    { key: "data_odbioru", label: "Data odbioru", type: "date", list: false },
    { key: "podpisane", label: "Czy dokument jest podpisany", type: "bool", list: false },
  ],
  hints: "Potwierdzenie odbioru dokumentów z nagłówkiem POTWIERDZENIE ODBIORU. Pole numer to numer potwierdzenia, pole data_odbioru to data odbioru. Pole podpisane: true, jeśli pod potwierdzeniem jest podpis.",
};

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

let uid = 0;
/** Etykieta + kontrolka + podpowiedź + miejsce na błąd, połączone przez aria-describedby. */
function fieldBox(labelText, control, hint) {
  const id = control.id || (control.id = `wiz-${++uid}`);
  const err = h("p", { class: "wiz-err", id: `${id}-err` });
  const hintEl = hint ? h("p", { class: "wiz-hint", id: `${id}-hint`, text: hint }) : null;
  control.setAttribute("aria-describedby", [hintEl?.id, err.id].filter(Boolean).join(" "));
  control._err = err;
  return h("div", { class: "wiz-field" }, h("label", { class: "wiz-label", for: id, text: labelText }), control, hintEl, err);
}

function step(no, title, intro, ...body) {
  return h("li", { class: "wiz-step" },
    h("span", { class: "wiz-no", "aria-hidden": "true", text: String(no) }),
    h("div", { class: "wiz-body" },
      h("h4", {}, h("span", { class: "sr-only", text: `Krok ${no}: ` }), title),
      intro ? h("p", { class: "wiz-intro", text: intro }) : null,
      ...body));
}

function downloadBlob(name, blob) {
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function existingIds() {
  return [...document.querySelectorAll("#types-list .type-head code")]
    .map((c) => c.textContent.trim().replace(/\.yaml$/, ""));
}

function mountWizard(root) {
  const touched = new Set();
  let showAll = false;
  const rows = [];

  const input = (attrs) => h("input", { class: "wiz-in", type: "text", autocomplete: "off", spellcheck: "false", ...attrs });
  const area = (attrs) => h("textarea", { class: "wiz-in", rows: "3", spellcheck: "false", ...attrs });

  const labelIn = input({ name: "label", placeholder: "np. Potwierdzenie odbioru", spellcheck: "true" });
  const idIn = input({ name: "id", class: "wiz-in wiz-mono", placeholder: "np. potwierdzenie_odbioru", "data-auto": "1" });
  const posIn = area({ name: "positive", placeholder: "Potwierdzenie odbioru\nData odbioru" });
  const negIn = area({ name: "negative", rows: "2", placeholder: "np. Wezwanie do odbioru" });
  const minIn = input({ name: "minimum", type: "number", class: "wiz-in wiz-num", min: "1", step: "1", value: "1", inputmode: "numeric" });
  const regexIn = h("input", { type: "checkbox", name: "regex" });
  const hintsIn = area({ name: "hints", rows: "4", spellcheck: "true" });
  const fieldsBox = h("div", { class: "wiz-fields" },
    h("div", { class: "wiz-frow wiz-fhead", "aria-hidden": "true" },
      h("span", { text: "Klucz w JSON" }), h("span", { text: "Etykieta po polsku" }),
      h("span", { text: "Typ wartości" }), h("span", { text: "Lista" }), h("span")));
  const fieldsErr = h("p", { class: "wiz-err", id: "wiz-fields-err" });

  const todo = h("div", { class: "wiz-todo" });
  const warn = h("div", { class: "wiz-warn" });
  const yamlName = h("code");
  const schemaName = h("code");
  const yamlPre = h("pre", { class: "json wiz-pre", tabindex: "0", "aria-label": "Podgląd pliku konfiguracji YAML" });
  const schemaPre = h("pre", { class: "json wiz-pre", tabindex: "0", "aria-label": "Podgląd schematu JSON" });

  const openBtn = h("button", { class: "btn", type: "button", onclick: () => toggle(true) }, "+ Dodaj typ dokumentu");
  const launch = h("div", { class: "wiz-launch" }, openBtn,
    h("p", { text: "Formularz przygotuje oba pliki konfiguracyjne. Nie trzeba ręcznie pisać YAML ani JSON." }));

  const form = h("form", { class: "wiz", hidden: true, novalidate: true, "aria-labelledby": "wiz-title", onsubmit: (e) => e.preventDefault() },
    h("div", { class: "wiz-head" },
      h("h3", { id: "wiz-title", text: "Nowy typ dokumentu" }),
      h("button", { class: "link-btn", type: "button", onclick: fillExample }, "Wypełnij przykładem"),
      h("button", { class: "link-btn", type: "button", onclick: reset }, "Wyczyść"),
      h("button", { class: "link-btn", type: "button", onclick: () => toggle(false) }, "Zamknij")),
    h("ol", { class: "wiz-steps" },
      step(1, "Nazwa", null,
        h("div", { class: "wiz-pair" },
          fieldBox("Nazwa wyświetlana", labelIn, "Tak typ będzie podpisany w panelu."),
          fieldBox("Identyfikator typu", idIn, "Małe litery bez polskich znaków, cyfry i podkreślenie. Od niego pochodzą nazwy plików. Uzupełnia się sam z nazwy."))),
      step(2, "Rozpoznawanie dokumentu",
        "Frazy, po których system pozna ten rodzaj dokumentu bez modelu językowego. Wielkość liter i odstępy nie mają znaczenia; sprawdzane są pierwsze trzy strony.",
        fieldBox("Frazy występujące w dokumencie (jedna w wierszu)", posIn),
        fieldBox("Frazy wykluczające (opcjonalnie)", negIn, "Jeśli w dokumencie jest któraś z nich, nie zostanie uznany za ten typ."),
        h("div", { class: "wiz-pair" },
          fieldBox("Ile różnych fraz musi się znaleźć", minIn),
          h("div", { class: "wiz-field wiz-check" },
            h("label", { class: "choice" }, regexIn, h("span", { class: "choice-box", "aria-hidden": "true" }), "Wpisuję wyrażenia regularne Pythona (dla zaawansowanych)")))),
      step(3, "Pola danych",
        "Co ma trafić do pliku JSON. Klucz to nazwa w JSON-ie, etykieta mówi modelowi, czego szukać. „Lista” oznacza wiele wartości, np. kilka numerów faktur.",
        fieldsBox, fieldsErr,
        h("button", { class: "btn btn-line wiz-add", type: "button", onclick: () => { addRow().key.focus(); update(); } }, "+ Dodaj pole")),
      step(4, "Wskazówki dla modelu",
        "Jak rozpoznać dokument i jak wypełniać pola. Gdy zostawisz puste, kreator wpisze wskazówki ogólne (widać je w podglądzie).",
        fieldBox("Wskazówki (opcjonalnie)", hintsIn)),
      step(5, "Pliki do pobrania", null,
        todo, warn,
        h("div", { class: "wiz-file" },
          h("div", { class: "wiz-file-head" }, yamlName,
            h("button", { class: "btn btn-line", type: "button", onclick: () => download("yaml") }, "Pobierz YAML")),
          yamlPre),
        h("div", { class: "wiz-file" },
          h("div", { class: "wiz-file-head" }, schemaName,
            h("button", { class: "btn btn-line", type: "button", onclick: () => download("schema") }, "Pobierz schemat")),
          schemaPre),
        h("div", { class: "wiz-actions" },
          h("button", { class: "btn", type: "button", onclick: () => download("zip") }, "Pobierz oba pliki (ZIP)")),
        h("h4", { text: "Gdzie wrzucić pliki" }),
        h("ol", { class: "wiz-where" },
          h("li", {}, "Rozpakuj ZIP w głównym katalogu projektu. Pliki trafią do ", h("code", { text: "configs/documents/" }), " i ", h("code", { text: "schemas/" }), ". Możesz też skopiować oba pliki ręcznie."),
          h("li", { text: "Uruchom ponownie backend. Przy starcie sprawdza wszystkie konfiguracje i w razie błędu zatrzymuje się z opisem problemu." }),
          h("li", { text: "Przetestuj nowy typ na kilku przykładowych PDF-ach oraz na dokumentach innych typów." })))));

  root.replaceChildren(launch, form);
  const manualSteps = root.closest("#view-types")?.querySelector(".help-steps");

  function addRow(data = {}) {
    const n = ++uid;
    const key = input({ class: "wiz-in wiz-mono", placeholder: "np. numer_umowy", "aria-label": "Klucz w JSON", "data-auto": data.key ? null : "1", id: `wiz-key-${n}` });
    const label = input({ placeholder: "np. Numer umowy", "aria-label": "Etykieta po polsku", spellcheck: "true", id: `wiz-flabel-${n}` });
    const type = h("select", { class: "wiz-in", "aria-label": "Typ wartości" },
      Object.entries(FIELD_TYPES).map(([value, t]) => h("option", { value, text: t.label })));
    const list = h("input", { type: "checkbox", "aria-label": "Lista (wiele wartości)" });
    key.value = data.key ?? "";
    label.value = data.label ?? "";
    type.value = data.type ?? "text";
    list.checked = !!data.list;
    const row = { key, label, type, list };
    const del = h("button", { class: "wiz-del", type: "button", "aria-label": "Usuń pole", title: "Usuń pole", onclick: () => {
      rows.splice(rows.indexOf(row), 1);
      row.el.remove();
      (rows[0]?.label ?? form.querySelector(".wiz-add")).focus();
      update();
    } }, "×");
    row.el = h("div", { class: "wiz-frow" }, key, label, type,
      h("label", { class: "choice" }, list, h("span", { class: "choice-box", "aria-hidden": "true" }), h("span", { class: "wiz-list-txt", text: "lista" })),
      del);
    label.addEventListener("input", () => { if (key.dataset.auto) key.value = slugify(label.value); });
    key.addEventListener("input", () => { key.dataset.auto = key.value ? "" : "1"; });
    rows.push(row);
    fieldsBox.append(row.el);
    return row;
  }

  function readSpec() {
    return {
      label: labelIn.value,
      id: idIn.value.trim(),
      positive: posIn.value,
      negative: negIn.value,
      regex: regexIn.checked,
      minimum: Number(minIn.value),
      fields: rows.map((r) => ({ key: r.key.value.trim(), label: r.label.value, type: r.type.value, list: r.list.checked })),
      hints: hintsIn.value,
    };
  }

  function targetEl(target) {
    const [kind, i] = target.split(":");
    if (kind === "key") return rows[i]?.key;
    if (kind === "flabel") return rows[i]?.label;
    return { label: labelIn, id: idIn, positive: posIn, negative: negIn, minimum: minIn }[kind] ?? null;
  }

  function update() {
    const spec = readSpec();
    const { errors, warnings } = validate(spec, existingIds());

    // błędy przy polach: po opuszczeniu pola albo po próbie pobrania
    const controls = [labelIn, idIn, posIn, negIn, minIn, ...rows.flatMap((r) => [r.key, r.label])];
    controls.forEach((c) => { c.removeAttribute("aria-invalid"); if (c._err) c._err.textContent = ""; });
    fieldsErr.textContent = "";
    const rowErrs = new Map();
    for (const e of errors) {
      if (e.target === "fields") { if (showAll) fieldsErr.textContent = e.msg; continue; }
      const el = targetEl(e.target);
      if (!el || !(showAll || touched.has(el))) continue;
      el.setAttribute("aria-invalid", "true");
      if (el._err) el._err.textContent ||= e.msg;
      else rowErrs.set(el, e.msg);
    }
    if (rowErrs.size) fieldsErr.textContent = [...new Set(rowErrs.values())].join(" ");

    todo.className = errors.length ? "wiz-todo" : "wiz-ready";
    todo.replaceChildren(errors.length
      ? h("div", {}, h("strong", { text: `Do uzupełnienia przed pobraniem (${errors.length}):` }), h("ul", {}, errors.map((e) => h("li", { text: e.msg }))))
      : h("span", { text: "Wszystko gotowe. Pliki są zgodne z formatem backendu." }));
    warn.replaceChildren(...warnings.map((w) => h("p", { text: w.msg })));
    warn.hidden = !warnings.length;

    const id = spec.id || "nowy_typ";
    yamlName.textContent = `configs/documents/${id}.yaml`;
    schemaName.textContent = `schemas/${id}.schema.json`;
    yamlPre.textContent = buildYaml(spec);
    schemaPre.textContent = schemaText(spec);
    hintsIn.placeholder = defaultInstructions(spec);
    return { spec, errors };
  }

  function download(what) {
    showAll = true;
    const { spec, errors } = update();
    if (errors.length) {
      const first = errors.map((e) => (e.target === "fields" ? form.querySelector(".wiz-add") : targetEl(e.target))).find(Boolean);
      first?.focus();
      return;
    }
    const [yaml, schema] = filesOf(spec);
    const base = (f) => f.name.split("/").pop();
    if (what === "yaml") downloadBlob(base(yaml), new Blob([yaml.text], { type: "application/yaml" }));
    else if (what === "schema") downloadBlob(base(schema), new Blob([schema.text], { type: "application/json" }));
    else downloadBlob(`typ_${spec.id}.zip`, zipStore([yaml, schema]));
  }

  function load(spec) {
    labelIn.value = spec.label ?? "";
    idIn.value = spec.id ?? slugify(spec.label ?? "");
    idIn.dataset.auto = idIn.value ? "" : "1";
    posIn.value = spec.positive ?? "";
    negIn.value = spec.negative ?? "";
    regexIn.checked = !!spec.regex;
    minIn.value = String(spec.minimum ?? 1);
    hintsIn.value = spec.hints ?? "";
    rows.splice(0).forEach((r) => r.el.remove());
    (spec.fields?.length ? spec.fields : [{}]).forEach((f) => addRow(f));
    touched.clear();
    showAll = false;
    update();
  }

  function fillExample() { load(EXAMPLE); labelIn.focus(); }
  function reset() { load({}); labelIn.focus(); }

  function toggle(open) {
    form.hidden = !open;
    launch.hidden = open;
    if (manualSteps) manualSteps.hidden = open;
    if (open) { update(); labelIn.focus(); } else openBtn.focus();
  }

  labelIn.addEventListener("input", () => { if (idIn.dataset.auto) idIn.value = slugify(labelIn.value); });
  idIn.addEventListener("input", () => { idIn.dataset.auto = idIn.value ? "" : "1"; });
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("focusout", (e) => {
    if (e.target.matches?.(".wiz-in") && e.target.value !== "") { touched.add(e.target); update(); }
  });

  load({});
}

if (typeof document !== "undefined") {
  const root = document.getElementById("type-wizard");
  if (root) mountWizard(root);
}
