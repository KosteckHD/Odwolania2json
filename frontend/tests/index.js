// Punkt wejścia dla `node --test frontend/tests/`.
// Od Node 21 argumenty --test są wzorcami glob, a sam katalog Node ładuje jak moduł
// (czyli ten plik). Stąd wczytujemy wszystkie *.test.mjs z tego katalogu.
const { readdirSync } = require("node:fs");

for (const name of readdirSync(__dirname).filter((n) => n.endsWith(".test.mjs")).sort()) {
  import(`./${name}`);
}
