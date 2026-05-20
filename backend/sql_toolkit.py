from __future__ import annotations

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model

from .config import settings


def build_sql_toolkit() -> SQLDatabaseToolkit:
    """
    Optional LangChain SQL toolkit hook.

    The app's default SQL path uses curated queries because model-generated SQL
    should run only against tightly scoped read-only users/views. Use this helper
    when you want to expose LangChain SQL tools behind that same database role.
    """
    db = SQLDatabase.from_uri(
        settings.database_url,
        include_tables=["enterprise_records", "event_logs", "audit_events"],
        sample_rows_in_table_info=2,
    )
    llm = init_chat_model(settings.chat_model)
    return SQLDatabaseToolkit(db=db, llm=llm)
