from src.llm import build_context, is_configured
from src.database import as_document, digest_resources


def test_source_context():
    rows = [{"Resource Name": "Example Food Pantry", "Services Provided": "Groceries"}]
    assert "[source 1]" in build_context(rows)
    assert "Example Food Pantry" in build_context(rows)


def test_embedding_document():
    assert "Groceries" in as_document({"Services Provided": "Groceries"})


def test_digests_stable():
    assert digest_resources([{"x": 1}]) == digest_resources([{"x": 1}])
