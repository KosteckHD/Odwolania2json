import re

from .contracts import ClassificationResult, DocumentConfig, ExtractedDocument


def classify(document: ExtractedDocument, configs: tuple[DocumentConfig, ...]) -> ClassificationResult:
    text = "\n".join(page.text for page in document.pages[:3])
    matches = {}
    for config in configs:
        if any(re.search(pattern, text) for pattern in config.negative_patterns):
            continue
        score = sum(bool(re.search(pattern, text)) for pattern in config.positive_patterns)
        if score >= config.minimum_matches:
            matches[config.doc_type] = score

    if not matches:
        return ClassificationResult("unknown", "no_match")
    best_score = max(matches.values())
    winners = [doc_type for doc_type, score in matches.items() if score == best_score]
    if len(winners) != 1:
        return ClassificationResult("unknown", "ambiguous")
    return ClassificationResult(winners[0], "matched")
