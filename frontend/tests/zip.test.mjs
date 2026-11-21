// Testy minimalnego ZIP-a (metoda „store”) z zip.js.
import { test } from "node:test";
import assert from "node:assert/strict";
import { crc32, zipStore } from "../zip.js";

const enc = new TextEncoder();
const dec = new TextDecoder();

test("crc32: znany wektor testowy", () => {
  assert.equal(crc32(enc.encode("123456789")), 0xCBF43926);
  assert.equal(crc32(new Uint8Array()), 0);
});

test("zipStore: sygnatury ZIP, nazwy plików i treść", async () => {
  const files = [
    { name: "sprawa/odwolanie.json", text: '{"a":1}' },
    { name: "sprawa/pełnomocnictwo.json", text: '{"zażółć":"gęślą"}' },
  ];
  const blob = zipStore(files);
  assert.equal(blob.type, "application/zip");

  const bytes = new Uint8Array(await blob.arrayBuffer());
  const view = new DataView(bytes.buffer);

  // nagłówek lokalny pierwszego pliku: „PK\x03\x04”
  assert.deepEqual([...bytes.slice(0, 4)], [0x50, 0x4B, 0x03, 0x04]);

  // koniec katalogu centralnego: ostatnie 22 bajty
  const end = bytes.length - 22;
  assert.equal(view.getUint32(end, true), 0x06054B50);
  assert.equal(view.getUint16(end + 10, true), files.length);
  const centralSize = view.getUint32(end + 12, true);
  const centralOffset = view.getUint32(end + 16, true);
  assert.equal(centralOffset + centralSize, end);

  // nagłówki lokalne po kolei: nazwa, CRC, rozmiar i treść
  let offset = 0;
  for (const file of files) {
    assert.equal(view.getUint32(offset, true), 0x04034B50);
    const crc = view.getUint32(offset + 14, true);
    const size = view.getUint32(offset + 18, true);
    const nameLength = view.getUint16(offset + 26, true);
    const name = dec.decode(bytes.slice(offset + 30, offset + 30 + nameLength));
    const data = bytes.slice(offset + 30 + nameLength, offset + 30 + nameLength + size);
    assert.equal(name, file.name);
    assert.equal(dec.decode(data), file.text);
    assert.equal(crc, crc32(enc.encode(file.text)));
    offset += 30 + nameLength + size;
  }
  assert.equal(offset, centralOffset);

  // katalog centralny wskazuje te same nazwy
  let pos = centralOffset;
  for (const file of files) {
    assert.equal(view.getUint32(pos, true), 0x02014B50);
    const nameLength = view.getUint16(pos + 28, true);
    assert.equal(dec.decode(bytes.slice(pos + 46, pos + 46 + nameLength)), file.name);
    pos += 46 + nameLength;
  }
});
