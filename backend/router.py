from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Route(str, Enum):
    DOCS = "docs"
    SQL = "sql"
    EVENTS = "events"
    AUDIT = "audit"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    confidence: float
    reason: str


SQL_TERMS = {
    "count",
    "sum",
    "average",
    "avg",
    "total",
    "latest",
    "oldest",
    "trend",
    "status",
    "quarter",
    "revenue",
    "amount",
    "rows",
    "table",
}
EVENT_TERMS = {"log", "logs", "alert", "alerts", "incident", "error", "service", "outage"}
AUDIT_TERMS = {"audit", "changed", "change", "before", "after", "who", "permission", "access"}
DOC_TERMS = {"policy", "document", "report", "pdf", "manual", "guideline", "explain", "summarize"}


def route_question(question: str) -> RouteDecision:
    q = question.lower()
    scores = {
        Route.SQL: sum(term in q for term in SQL_TERMS),
        Route.EVENTS: sum(term in q for term in EVENT_TERMS),
        Route.AUDIT: sum(term in q for term in AUDIT_TERMS),
        Route.DOCS: sum(term in q for term in DOC_TERMS),
    }
    active = [route for route, score in scores.items() if score > 0]
    if len(active) > 1:
        return RouteDecision(Route.HYBRID, 0.74, f"Multiple source hints matched: {', '.join(r.value for r in active)}")
    if active:
        route = active[0]
        return RouteDecision(route, 0.82, f"Matched {route.value} retrieval terms")
    return RouteDecision(Route.DOCS, 0.55, "Defaulted to semantic document retrieval")
