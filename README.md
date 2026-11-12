# CivaMap — conversational resource assistant

Streamlit chat interface + Qdrant retrieval + Colby-hosted Qwen (OpenAI-compatible API).
The bundled Excel file is the source directory for local development; its resource details
may be outdated or incomplete. Confirm eligibility and availability with providers.

## Quickstart (Mac)

```bash
cd ~/Documents/civamap
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with the **exact** Qwen API base URL, model ID, and (if needed) key provided by Colby.
`QWEN_MODEL=qwen-3.8-27b` is a provisional name from the original email, **not a verified API model ID**.
`QWEN_BASE_URL` normally ends in `/v1`, but use whatever format Colby confirms.
If your gateway doesn't require auth, you may leave `QWEN_API_KEY` blank.
Then:

```bash
streamlit run app.py
```

Open http://localhost:8501 and ask questions. First startup downloads the FastEmbed model
(`BAAI/bge-small-en-v1.5`) from a model repository; subsequent embedding runs locally.
Qdrant runs in embedded persistent mode in `.qdrant/` by default. No Docker is required.

## Accessing Colby's managed Qdrant

If the professor provides Qdrant credentials, set `QDRANT_URL` and optionally
`QDRANT_API_KEY` in `.env`. Otherwise stay with local Qdrant for the prototype.
If you change the Excel file, the app reindexes automatically on restart. Click
**Rebuild resource index** in the sidebar to force a reindex.

## Architecture

- `app.py` — Streamlit conversational UI and session history
- `src/retrieval.py` — spreadsheet reader and keyword ranker
- `src/database.py` — local/remote Qdrant, FastEmbed, hybrid score fusion
- `src/llm.py` — prompt, grounded directory context, Qwen request
- `data/resource_directory.xlsx` — provided resource directory
- `.env` — secret endpoint settings; **never commit**

## Data safety and limitations

Do not push the directory to a public repository, upload it to public Qdrant,
or deploy this app publicly until Colby approves the data and user-query handling.
All retrieved source text is treated as reference material, not as instructions.
Chat history lives only in the current Streamlit browser session, but chat content
is transmitted to the configured LLM endpoint. The embedding model initially
requires a download; embedding and index generation then happen in the local process.

The prototype uses dense vector retrieval fused with a local keyword ranker (not
Qdrant-native dense+sparse vector hybrid). This is a useful starting point, not a
production-ready referral system. Qdrant's local storage supports one app process
at a time; use a Qdrant server for multi-user deployment. There is no fallback
pretending that a keyword result is a model answer when Qwen is not configured.

## Tests

```bash
python -m pytest tests -q
```

## Colby-blue UI and Maps

Streamlit is themed with Colby Blue (`#002169`) in `.streamlit/config.toml`.
The right-hand panel shows a Google Maps **place search** for directory matches
that have a non-statewide service area, plus links to open Google Maps and get
directions using the visitor's location (subject to their browser/Maps permissions).
No Google Maps API key or GPS permission is needed for CivaMap itself.

**Important:** The workbook has service areas, not verified street addresses or
coordinates. A map result may be approximate or ambiguous; confirm the precise
site with the provider. Statewide resources are not assigned arbitrary pins.
Google Maps may require an internet connection, and embedding can be limited by
browser/network restrictions. If an embedded map doesn't load, use the open-in-Maps link.
