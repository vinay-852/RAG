from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import JSONLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.psycopg import register_vector

from .config import ROOT_DIR, settings
from .db import get_conn, run_schema
from .embeddings import embedder
from .llm_client import markitdown_llm_client


STRUCTURED_COLUMNS = {
    "record_type",
    "business_unit",
    "owner_department",
    "status",
    "summary",
}
EVENT_COLUMNS = {"event_type", "event_ts", "message"}
DOCUMENT_SUFFIXES = {
    ".csv",
    ".doc",
    ".docx",
    ".html",
    ".htm",
    ".json",
    ".md",
    ".pdf",
    ".ppt",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsx",
}


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def _roles(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split("|") if item.strip()]


def _data_files(root: Path) -> list[Path]:
    return sorted(
        file_path
        for file_path in root.rglob("*")
        if file_path.is_file() and not file_path.name.endswith(".meta.json")
    )


def _sidecar_metadata(file_path: Path) -> dict[str, Any]:
    meta_path = file_path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text())


def _csv_headers(file_path: Path) -> set[str]:
    try:
        with file_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            return set(reader.fieldnames or [])
    except Exception:
        return set()


def _jsonl_first_record(file_path: Path) -> dict[str, Any]:
    try:
        with file_path.open() as handle:
            for line in handle:
                if line.strip():
                    return json.loads(line)
    except Exception:
        return {}
    return {}


def discover_data_sources(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    document_files: list[Path] = []
    structured_files: list[Path] = []
    event_files: list[Path] = []

    for file_path in _data_files(root):
        suffix = file_path.suffix.lower()
        if suffix == ".csv" and STRUCTURED_COLUMNS.issubset(_csv_headers(file_path)):
            structured_files.append(file_path)
        elif suffix == ".jsonl" and EVENT_COLUMNS.issubset(set(_jsonl_first_record(file_path))):
            event_files.append(file_path)
        elif suffix in DOCUMENT_SUFFIXES or suffix == ".jsonl":
            document_files.append(file_path)
        else:
            print(f"Skipping {file_path}: unsupported data file type")

    return document_files, structured_files, event_files


def seed_identity() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tenants (id, name) VALUES
                ('acme', 'Acme Enterprise')
            ON CONFLICT (id) DO NOTHING;

            INSERT INTO roles (id, label, description) VALUES
                ('employee', 'Employee', 'General internal access'),
                ('finance', 'Finance', 'Finance records and reports'),
                ('security', 'Security', 'Security logs and incidents'),
                ('compliance', 'Compliance', 'Audit and regulatory material'),
                ('executive', 'Executive', 'Broad executive visibility')
            ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, description = EXCLUDED.description;

            INSERT INTO app_users (id, email, display_name, department, tenant_id) VALUES
                ('u_ava', 'ava@acme.example', 'Ava Finance', 'Finance', 'acme'),
                ('u_noah', 'noah@acme.example', 'Noah Security', 'Security', 'acme'),
                ('u_mira', 'mira@acme.example', 'Mira Compliance', 'Compliance', 'acme'),
                ('u_eli', 'eli@acme.example', 'Eli Employee', 'Operations', 'acme')
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                display_name = EXCLUDED.display_name,
                department = EXCLUDED.department,
                tenant_id = EXCLUDED.tenant_id;

            INSERT INTO user_roles (user_id, role_id) VALUES
                ('u_ava', 'employee'), ('u_ava', 'finance'),
                ('u_noah', 'employee'), ('u_noah', 'security'),
                ('u_mira', 'employee'), ('u_mira', 'compliance'),
                ('u_eli', 'employee')
            ON CONFLICT DO NOTHING;
            """
        )
        conn.commit()


def load_documents(path: Path, files: list[Path] | None = None) -> list[Document]:
    docs: list[Document] = []
    try:
        from markitdown import MarkItDown
    except Exception:
        MarkItDown = None

    document_files = files or _data_files(path)
    for file_path in document_files:
        if file_path.is_dir() or file_path.name.endswith(".meta.json"):
            continue
        metadata = _sidecar_metadata(file_path)
        if MarkItDown:
            md = MarkItDown(
                enable_plugins=True,
                llm_client=markitdown_llm_client(),
                llm_model=settings.llm_model,
            )
            try:
                result = md.convert(str(file_path))
                content = result.text_content
            except Exception as exc:
                print(f"Skipping {file_path}: MarkItDown conversion failed: {exc}")
                continue
        else:
            if file_path.suffix.lower() not in {".md", ".txt", ".csv", ".json", ".jsonl"}:
                print(f"Skipping {file_path}: MarkItDown is not installed")
                continue
            content = file_path.read_text(errors="ignore")
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "title": metadata.get("title", file_path.stem.replace("_", " ").title()),
                    "source_uri": str(file_path.relative_to(ROOT_DIR)),
                    "source_type": file_path.suffix.lstrip(".") or "text",
                    "classification": metadata.get("classification", "internal"),
                    "tenant_id": metadata.get("tenant_id", "acme"),
                    "allowed_roles": metadata.get("allowed_roles", ["employee"]),
                },
            )
        )
    return docs


def ingest_documents(path: Path, files: list[Path] | None = None) -> int:
    docs = load_documents(path, files)
    if not docs:
        return 0
    chunks = _splitter().split_documents(docs)
    texts = [chunk.page_content for chunk in chunks]
    embeddings = embedder.embed_many(texts)
    with get_conn() as conn:
        register_vector(conn)
        chunk_counts: dict[str, int] = {}
        for chunk, vector in zip(chunks, embeddings, strict=True):
            meta = chunk.metadata
            source_key = f"{meta['tenant_id']}::{meta['source_uri']}::{meta['title']}"
            chunk_index = chunk_counts.get(source_key, 0)
            chunk_counts[source_key] = chunk_index + 1
            row = conn.execute(
                """
                INSERT INTO documents (tenant_id, title, source_uri, source_type, classification, allowed_roles)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    meta["tenant_id"],
                    meta["title"],
                    meta["source_uri"],
                    meta["source_type"],
                    meta["classification"],
                    meta["allowed_roles"],
                ),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT id FROM documents WHERE source_uri = %s AND title = %s",
                    (meta["source_uri"], meta["title"]),
                ).fetchone()
            conn.execute(
                """
                INSERT INTO document_chunks (document_id, tenant_id, chunk_index, content, metadata, allowed_roles, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    allowed_roles = EXCLUDED.allowed_roles,
                    embedding = EXCLUDED.embedding
                """,
                (
                    row["id"],
                    meta["tenant_id"],
                    chunk_index,
                    chunk.page_content,
                    json.dumps(meta),
                    meta["allowed_roles"],
                    vector,
                ),
            )
        conn.commit()
    return len(chunks)


def ingest_structured(path: Path, files: list[Path] | None = None) -> int:
    count = 0
    csv_files = files or sorted(path.glob("*.csv"))
    with get_conn() as conn:
        for csv_path in csv_files:
            with csv_path.open(newline="") as handle:
                for row in csv.DictReader(handle):
                    conn.execute(
                        """
                        INSERT INTO enterprise_records
                            (tenant_id, record_type, business_unit, owner_department, fiscal_quarter, status, amount, summary, payload, allowed_roles)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            row.get("tenant_id", "acme"),
                            row["record_type"],
                            row["business_unit"],
                            row["owner_department"],
                            row.get("fiscal_quarter") or None,
                            row["status"],
                            row.get("amount") or None,
                            row["summary"],
                            json.dumps(row),
                            _roles(row.get("allowed_roles", "employee")),
                        ),
                    )
                    count += 1
        conn.commit()
    return count


def ingest_events(path: Path, files: list[Path] | None = None) -> int:
    count = 0
    docs: list[Document] = []
    event_files = files or sorted(path.glob("*.jsonl"))
    for jsonl_path in event_files:
        loader = JSONLoader(
            file_path=str(jsonl_path),
            jq_schema=".",
            content_key="message",
            text_content=False,
            json_lines=True,
            metadata_func=_event_metadata,
        )
        docs.extend(loader.load())
    rows = [doc.metadata["event"] for doc in docs]
    embeddings = embedder.embed_many([doc.page_content for doc in docs])
    with get_conn() as conn:
        register_vector(conn)
        for row, vector in zip(rows, embeddings, strict=True):
            if row.get("event_type") == "audit":
                conn.execute(
                    """
                    INSERT INTO audit_events
                        (tenant_id, event_ts, actor, action, object_type, object_id, before_value, after_value, reason, allowed_roles)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.get("tenant_id", "acme"),
                        row["event_ts"],
                        row["actor"],
                        row["action"],
                        row["object_type"],
                        row["object_id"],
                        json.dumps(row.get("before")),
                        json.dumps(row.get("after")),
                        row.get("reason"),
                        _roles(row.get("allowed_roles", ["compliance"])),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO event_logs
                        (tenant_id, event_ts, service, level, actor, action, resource, message, raw, allowed_roles, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.get("tenant_id", "acme"),
                        row["event_ts"],
                        row["service"],
                        row["level"],
                        row.get("actor"),
                        row["action"],
                        row["resource"],
                        row["message"],
                        json.dumps(row),
                        _roles(row.get("allowed_roles", ["security"])),
                        vector,
                    ),
                )
            count += 1
        conn.commit()
    return count


def _event_metadata(record: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    metadata["event"] = record
    metadata["tenant_id"] = record.get("tenant_id", "acme")
    metadata["event_type"] = record.get("event_type", "log")
    metadata["allowed_roles"] = record.get("allowed_roles", [])
    return metadata


def reset_data() -> None:
    with get_conn() as conn:
        conn.execute("TRUNCATE document_chunks, documents, enterprise_records, event_logs, audit_events RESTART IDENTITY CASCADE")
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest enterprise RAG demo data")
    parser.add_argument("--reset", action="store_true", help="Clear content tables before ingesting")
    args = parser.parse_args()
    run_schema(ROOT_DIR / "backend" / "sql" / "schema.sql")
    seed_identity()
    if args.reset:
        reset_data()
    data_root = ROOT_DIR / "data"
    document_files, structured_files, event_files = discover_data_sources(data_root)
    print(
        "Discovered "
        f"{len(document_files)} document files, "
        f"{len(structured_files)} structured files, "
        f"{len(event_files)} event files under {data_root}"
    )
    doc_count = ingest_documents(data_root, document_files)
    record_count = ingest_structured(data_root, structured_files)
    event_count = ingest_events(data_root, event_files)
    print(f"Ingested {doc_count} chunks, {record_count} records, {event_count} events")


if __name__ == "__main__":
    main()
