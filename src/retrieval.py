"""Simple local search over the directory; replace with Qdrant retrieval later."""

from collections import Counter
from functools import lru_cache
from pathlib import Path
import re

import pandas as pd

FIELDS = (
    "Resource Name", "Category", "Services Provided", "Eligibility and Cost",
    "CHW Insider Tips", "Primary Service Area", "Phone / Contact",
    "Website / Resource Link", "Last Checked", "Search Text (for semantic search)",
)
STOPWORDS = {"i", "a", "an", "the", "to", "and", "or", "is", "am", "are", "my", "for", "of", "in", "on", "with", "me", "need", "help", "where", "can", "get", "find", "some", "how"}


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in STOPWORDS]


@lru_cache(maxsize=4)
def load_resources(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found. Place the workbook in the data folder.")
    frame = pd.read_excel(path, sheet_name="Resources", dtype=str).fillna("")
    missing = [field for field in FIELDS if field not in frame.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {', '.join(missing)}")
    return frame.to_dict(orient="records")


def search_resources(resources: list[dict[str, str]], query: str, category: str = "All categories", limit: int = 8) -> list[dict[str, str]]:
    filtered = [r for r in resources if category == "All categories" or r["Category"] == category]
    terms = tokens(query)
    if not terms:
        return filtered[:limit]
    scored = []
    for row in filtered:
        name = Counter(tokens(row["Resource Name"]))
        cat = Counter(tokens(row["Category"]))
        content = Counter(tokens(" ".join(str(row.get(k, "")) for k in (
            "Services Provided", "Eligibility and Cost", "CHW Insider Tips",
            "Primary Service Area", "Search Text (for semantic search)",
        ))))
        score = sum(5 * name[t] + 3 * cat[t] + min(content[t], 3) for t in set(terms))
        if score:
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["Resource Name"]))
    return [row for _, row in scored[:limit]]
