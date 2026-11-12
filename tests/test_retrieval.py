from src.retrieval import tokens, search_resources


def test_tokens_drop_common_words():
    assert tokens("I need help with heating") == ["heating"]


def test_rank_relevant_record():
    rows = [
        {"Resource Name": "Food Pantry", "Category": "Food", "Services Provided": "groceries", "Eligibility and Cost": "", "CHW Insider Tips": "", "Primary Service Area": "", "Search Text (for semantic search)": ""},
        {"Resource Name": "Heating Assistance", "Category": "Energy", "Services Provided": "heating oil", "Eligibility and Cost": "", "CHW Insider Tips": "", "Primary Service Area": "", "Search Text (for semantic search)": ""},
    ]
    assert search_resources(rows, "heating", limit=1)[0]["Resource Name"] == "Heating Assistance"
