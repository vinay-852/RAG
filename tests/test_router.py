from backend.router import Route, route_question


def test_routes_sql_questions() -> None:
    assert route_question("Count authorized records by status").route == Route.SQL


def test_routes_event_questions() -> None:
    assert route_question("Show recent security alerts for payment services").route == Route.EVENTS


def test_routes_audit_questions() -> None:
    assert route_question("Who changed vendor access policies?").route in {Route.AUDIT, Route.HYBRID}


def test_defaults_to_docs() -> None:
    assert route_question("Summarize access control exceptions").route in {Route.DOCS, Route.HYBRID}
