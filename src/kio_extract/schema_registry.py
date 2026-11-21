import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .contracts import ConfigurationError, DocumentConfig, FieldRule
from .normalization import NORMALIZERS
from .postprocess import validate_postprocess


def _patterns(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(isinstance(value, str) and value for value in raw):
        raise ConfigurationError("Oczekiwano listy wzorców regex")
    for pattern in raw:
        re.compile(pattern)
    return tuple(raw)


def _field_rules(raw: dict, schema: dict) -> dict[str, FieldRule]:
    fields = {}
    for path, settings in raw.items():
        leaf = schema
        for key in path.split("."):
            leaf = leaf.get("properties", {}).get(key)
            if not isinstance(leaf, dict):
                raise ConfigurationError(f"Ścieżka pola poza schematem: {path}")
        if leaf.get("type") in ("object", "array"):
            raise ConfigurationError(f"Reguła regex wymaga pola skalarnego: {path}")
        pattern = settings["pattern"]
        normalize = settings.get("normalize", "text")
        if normalize not in NORMALIZERS or "value" not in re.compile(pattern).groupindex:
            raise ConfigurationError(f"Reguła {path} wymaga grupy value i znanego normalizatora")
        fields[path] = FieldRule(pattern, normalize)
    return fields


def load_configs(config_dir: Path, schema_dir: Path) -> dict[str, DocumentConfig]:
    configs = {}
    for path in sorted(config_dir.glob("*.yaml")):
        try:
            settings = yaml.safe_load(path.read_text(encoding="utf-8"))
            doc_type = settings["id"]
            if not re.fullmatch(r"[a-z][a-z0-9_]*", doc_type) or doc_type in (*configs, "unknown"):
                raise ConfigurationError("Nieprawidłowy, powtórzony lub zastrzeżony identyfikator klasy")
            schema_name = settings["schema"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", schema_name):
                raise ConfigurationError("Schemat musi być nazwą pliku .json w katalogu schematów")
            schema = json.loads((schema_dir / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            if not isinstance(schema, dict) or schema.get("type") != "object":
                raise ConfigurationError("Schemat dokumentu musi opisywać obiekt JSON")
            classification = settings["classification"]
            positive = _patterns(classification["positive_patterns"])
            negative = _patterns(classification.get("negative_patterns", []))
            minimum = classification.get("minimum_matches", 1)
            if type(minimum) is not int or not 1 <= minimum <= len(set(positive)) or len(set(positive)) != len(positive):
                raise ConfigurationError("Nieprawidłowy próg lub powtórzone wzorce klasyfikacji")
            options = settings.get("options", {})
            fields = settings.get("fields", {})
            extractor = settings.get("extractor")
            if not isinstance(options, dict) or not isinstance(fields, dict):
                raise ConfigurationError("options i fields muszą być obiektami YAML")
            if extractor is not None and not re.fullmatch(r"[\w.]+:[A-Za-z_]\w*", extractor):
                raise ConfigurationError("Ekstraktor musi mieć postać modul:funkcja")
            configs[doc_type] = DocumentConfig(
                doc_type, schema, positive, negative, minimum, _field_rules(fields, schema), options, extractor,
                validate_postprocess(settings.get("postprocess"), schema, options),
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError, re.error, yaml.YAMLError, SchemaError, ConfigurationError) as exc:
            raise ConfigurationError(f"Błąd konfiguracji {path.name}: {exc}") from exc
    if not configs:
        raise ConfigurationError(f"Brak konfiguracji YAML w {config_dir}")
    return configs
