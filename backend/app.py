from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT_DIR, settings
from .db import close_pool, open_pool, run_schema
from .generation import generate_answer
from .retrieval import query_records, search_audits, search_documents, search_events
from .router import Route
from .router import route_question as decide_route
from .security import get_user_context


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    user_id: str = "u_eli"


class QueryResponse(BaseModel):
    answer: str
    route: str
    route_reason: str
    confidence: float
    user: dict
    sources: list[dict]


app = FastAPI(title="Enterprise RAG Intelligence", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin] if settings.cors_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = ROOT_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.on_event("startup")
def startup() -> None:
    open_pool()
    run_schema(ROOT_DIR / "backend" / "sql" / "schema.sql")


@app.on_event("shutdown")
def shutdown() -> None:
    close_pool()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/api/users")
def users() -> list[dict]:
    from .db import get_conn

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, u.department, coalesce(array_agg(ur.role_id), '{}') AS roles
            FROM app_users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            GROUP BY u.id
            ORDER BY u.display_name
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    try:
        user = get_user_context(request.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    decision = decide_route(request.question)
    sources = []
    sql_summary = None

    if decision.route == Route.SQL:
        sql_summary, sources = query_records(request.question, user)
    elif decision.route == Route.EVENTS:
        sources = search_events(request.question, user)
    elif decision.route == Route.AUDIT:
        sources = search_audits(request.question, user)
    elif decision.route == Route.HYBRID:
        sql_summary, sql_sources = query_records(request.question, user, limit=4)
        sources = sql_sources + search_documents(request.question, user, limit=3) + search_events(request.question, user, limit=3) + search_audits(request.question, user, limit=3)
    else:
        sources = search_documents(request.question, user)

    answer = generate_answer(request.question, user, decision, sources, sql_summary)
    return QueryResponse(
        answer=answer,
        route=decision.route.value,
        route_reason=decision.reason,
        confidence=decision.confidence,
        user={
            "id": user.user_id,
            "display_name": user.display_name,
            "department": user.department,
            "roles": user.roles,
        },
        sources=[
            {
                "type": source.source_type,
                "title": source.title,
                "score": round(source.score, 4),
                "preview": source.content[:320],
                "metadata": source.metadata,
            }
            for source in sources
        ],
    )
