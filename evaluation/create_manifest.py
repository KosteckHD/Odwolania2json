"""Create a reproducible case split for the published UZP training set."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    documents = []
    negative_hashes = {}
    names = {"odwolanie": "odwolanie", "pelnomocnictwo": "pelnomocnictwo", "potwierdzenie_przelewu": "przelew"}
    for case in sorted(args.data.glob("przyklad_*")):
        number = int(case.name.rsplit("_", 1)[1])
        split = "development" if number <= 42 else "validation" if number <= 54 else "test"
        for pdf in sorted(case.glob("*.pdf")):
            kind = names.get(pdf.stem, "unknown")
            entry = {"split": split, "type": kind, "prediction": pdf.relative_to(args.data).with_suffix(".json").as_posix()}
            if kind != "unknown":
                reference = case / f"{kind}.json"
                if not reference.is_file():
                    raise FileNotFoundError(reference)
                entry["reference"] = reference.relative_to(args.data).as_posix()
            else:
                digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
                if digest in negative_hashes and negative_hashes[digest] != split:
                    raise ValueError("Duplikat negatywu występuje w różnych podziałach spraw")
                negative_hashes[digest] = split
                entry["sha256"] = digest
            documents.append(entry)
    if not documents:
        raise ValueError("Nie znaleziono spraw")
    for pdf in sorted((args.data / "negatywne").glob("*.pdf")):
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        split = negative_hashes.setdefault(digest, "validation")
        documents.append({"split": split, "type": "unknown", "sha256": digest,
                          "prediction": pdf.relative_to(args.data).with_suffix(".json").as_posix()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"documents": documents}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zapisano {len(documents)} dokumentów do {args.output}")


if __name__ == "__main__":
    main()
