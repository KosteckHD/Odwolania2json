import json
from pathlib import Path
from shutil import copytree

import pytest
from jsonschema import Draft202012Validator

from kio_extract.classifier import classify
from kio_extract.contracts import DocumentConfig, ExtractedDocument, ExtractionResult, PageText
from kio_extract.extraction_engine import resolve_extractor
from kio_extract.prompt_extraction import PromptExtractor
from kio_extract.schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("sample", "expected_type"),
    [("odwolanie", "odwolanie"), ("pelnomocnictwo", "pelnomocnictwo"), ("przelew", "przelew"), ("negative", "unknown")],
)
def test_content_classification_and_extractor_contract(sample, expected_type):
    configs = load_configs(ROOT / "configs" / "documents", ROOT / "schemas")
    text = (ROOT / "tests" / "fixtures" / "contract_samples" / f"{sample}.txt").read_text(encoding="utf-8")
    document = ExtractedDocument(Path("nazwa_mylaca.pdf"), (PageText(1, text),))
    assert classify(document, tuple(configs.values())).doc_type == expected_type
    if expected_type != "unknown":
        config = configs[expected_type]
        result = resolve_extractor(config)(document, config)
        Draft202012Validator(config.schema).validate(result.data)
        assert isinstance(result.evidence, tuple)


def test_extension_with_only_yaml_and_schema(tmp_path):
    configs_path = tmp_path / "configs"
    schemas_path = tmp_path / "schemas"
    copytree(ROOT / "configs" / "documents", configs_path)
    copytree(ROOT / "schemas", schemas_path)
    schema = {
        "type": "object", "required": ["kod"], "additionalProperties": False,
        "properties": {"kod": {"type": ["string", "null"]}},
    }
    (schemas_path / "receipt.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (configs_path / "receipt.yaml").write_text(
        """id: receipt
schema: receipt.schema.json
classification:
  positive_patterns: ['^RECEIPT']
fields:
  kod:
    pattern: 'Kod: (?P<value>[0-9-]+)'
    normalize: digits
""",
        encoding="utf-8",
    )
    configs = load_configs(configs_path, schemas_path)
    assert set(configs) == {"odwolanie", "pelnomocnictwo", "przelew", "receipt"}
    document = ExtractedDocument(Path("odwolanie.pdf"), (PageText(1, "RECEIPT\nKod: 000-21"),))
    config = configs[classify(document, tuple(configs.values())).doc_type]
    result = resolve_extractor(config)(document, config)

    assert result.data == {"kod": "00021"}
    assert result.evidence[0].page_number == 1

    conflicting = ExtractedDocument(document.source_path, (*document.pages, PageText(2, "Kod: 000-22")))
    assert resolve_extractor(config)(conflicting, config) == ExtractionResult({"kod": None})


def mock_extract(document, config, llm=None):
    return ExtractionResult({"origin": document.pages[0].page_number})


def test_plugin_is_resolved_from_configuration():
    config = DocumentConfig("test", {}, extractor=f"{__name__}:mock_extract")
    document = ExtractedDocument(Path("fixture.pdf"), (PageText(1, "tekst"),))
    assert resolve_extractor(config)(document, config).data == {"origin": 1}


def test_fourth_class_instructions_and_schema_reach_llm(tmp_path):
    schema = {"type": "object", "required": ["kod"], "additionalProperties": False,
              "properties": {"kod": {"type": "string"}}}
    config = DocumentConfig("receipt", schema, options={"llm_instructions": "Dokument RECEIPT ma pole kod."})

    class Stub:
        def extract_json(self, *, instructions, text, schema):
            assert "Dokument RECEIPT ma pole kod." in instructions
            assert "receipt" in schema["properties"]["typ"]["enum"]
            return {"typ": "receipt", "dane": {"kod": "0001"}}

    prompt = tmp_path / "prompt.md"
    prompt.write_text("Wybierz klasę na podstawie konfiguracji.", encoding="utf-8")
    document = ExtractedDocument(Path("fixture.pdf"), (PageText(1, "RECEIPT 0001"),))
    classification, data = PromptExtractor(Stub(), (config,), prompt).extract(document)
    assert classification.doc_type == "receipt" and data == {"kod": "0001"}
