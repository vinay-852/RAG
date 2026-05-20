# Enterprise RAG Intelligence

End-to-end challenge implementation for secure, role-aware retrieval across enterprise documents, structured SQL data, JSON logs, and audit trails.

## What Is Implemented

- Postgres-centered storage with `pgvector`, JSONB, typed records, and RBAC tables.
- Document ingestion through MarkItDown-compatible files into LangChain `Document` objects, split into chunks, embedded, and stored in Postgres.
- Structured CSV ingestion into queryable enterprise tables.
- JSONL log and audit ingestion into event/audit tables, with semantic embeddings for logs.
- Query router for docs, SQL records, logs, audits, and hybrid questions.
- RBAC-aware retrieval that filters by tenant and allowed roles before generation.
- OpenAI answer generation with citations when `OPENAI_API_KEY` is set.
- Offline deterministic embeddings and extractive answers when no API key is set, so the demo still runs.
- FastAPI backend and a compact browser UI with route trace, confidence, and authorized sources.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000`.

You can also run:

```bash
./scripts/run_demo.sh
```

## Oracle / LiteLLM Endpoint

The app service is configured to call:

```text
https://code-internal.aiservice.us-chicago-1.oci.oraclecloud.com/20250206/app/litellm
```

Set `LLM_API_KEY` in `.env` when the endpoint requires bearer auth. Generation uses `LLM_MODEL=oca/gpt5` by default. The request path defaults to `chat/completions`, so the full URL is `${LLM_BASE_URL}/chat/completions`; override `LLM_COMPLETIONS_PATH` if your gateway exposes a different path. The OCA adapter is used when `LLM_MODEL` starts with `oca/` or `LLM_BASE_URL` points at the Oracle/LiteLLM gateway. The app sends the headers:

```text
client: codex-cli
client-version: 0
```

Streaming responses are parsed from `data:` lines in `backend/llm_client.py`, accumulating `choices[0].delta.content` until `[DONE]`.

MarkItDown uses the same configured model/client for image descriptions during ingestion:

```python
MarkItDown(
    enable_plugins=True,
    llm_client=markitdown_llm_client(),
    llm_model=settings.llm_model,
)
```

With the default `.env`, that means image descriptions also use `oca/gpt5` through the Oracle/LiteLLM gateway.

For normal OpenAI generation, set a non-OCA model and do not point `LLM_BASE_URL` at the Oracle gateway:

```bash
LLM_MODEL=gpt-4.1-mini
LLM_BASE_URL=
LLM_API_KEY=your_openai_key
```

That path uses the regular OpenAI SDK Responses API.

## Demo Users

- `Ava Finance`: employee, finance
- `Noah Security`: employee, security
- `Mira Compliance`: employee, compliance
- `Eli Employee`: employee

Ask the same question as different users to see RBAC filtering change the returned sources.

## Useful Questions

- `Which reports mention access control exceptions?`
- `Count authorized records by status`
- `Show recent security alerts for payment services`
- `Who changed vendor access policies?`
- `What is the total amount by business unit and quarter?`

## Architecture

```text
PDF/DOCX/PPTX/HTML/TXT/MD
  -> MarkItDown when installed
  -> LangChain Document
  -> RecursiveCharacterTextSplitter
  -> embeddings
  -> Postgres document_chunks with pgvector

CSV / structured records
  -> enterprise_records
  -> curated SQL retrieval
  -> optional LangChain SQLDatabaseToolkit hook

JSONL logs and audits
  -> event_logs / audit_events
  -> JSONB raw payloads
  -> SQL filters
  -> optional semantic search for log messages

Question
  -> query router
  -> RBAC-filtered retrieval
  -> grounded answer with source trace
```

## Security Notes

The app enforces tenant and role filters in SQL before text reaches the model. The default SQL path uses curated queries. `backend/sql_toolkit.py` provides a LangChain SQL toolkit hook for experimentation, but production use should run it against read-only users and restricted views.

For database-native hardening, add Postgres RLS policies on top of the existing role columns and connect through per-user or per-role database sessions.
