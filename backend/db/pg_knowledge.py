from __future__ import annotations

from collections.abc import Sequence

from db.models import DesignKnowledge, DesignKnowledgeFilter
from db.pg_utils import (
    ConnectionFactory,
    RowMapping,
    to_json_dict,
    to_list_str,
    to_optional_str,
    to_str,
)
from db.postgres import create_connection


class PostgresDesignKnowledgeRepository:
    def __init__(self, connection_factory: ConnectionFactory | None = None) -> None:
        self._connection_factory = connection_factory or create_connection

    def list_knowledge(
        self, knowledge_filter: DesignKnowledgeFilter
    ) -> Sequence[DesignKnowledge]:
        query, params = _build_knowledge_filter_query(knowledge_filter)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [_row_to_knowledge(row) for row in rows]


def _build_knowledge_filter_query(
    knowledge_filter: DesignKnowledgeFilter,
) -> tuple[str, dict[str, object]]:
    clauses = ["TRUE"]
    params: dict[str, object] = {}

    if knowledge_filter.tenant_id is not None:
        clauses.append("tenant_id = %(tenant_id)s")
        params["tenant_id"] = knowledge_filter.tenant_id
    if knowledge_filter.category:
        clauses.append("category = %(category)s")
        params["category"] = knowledge_filter.category
    if knowledge_filter.source:
        clauses.append("source = %(source)s")
        params["source"] = knowledge_filter.source
    if knowledge_filter.tags:
        clauses.append("tags @> %(tags)s::text[]")
        params["tags"] = knowledge_filter.tags

    where_clause = " AND ".join(clauses)
    query = f"SELECT * FROM design_knowledge WHERE {where_clause}"
    return query, params


def _row_to_knowledge(row: RowMapping) -> DesignKnowledge:
    return DesignKnowledge(
        id=to_str(row.get("id")),
        tenant_id=to_optional_str(row.get("tenant_id")),
        title=to_str(row.get("title")),
        content=to_str(row.get("content")),
        category=to_optional_str(row.get("category")),
        tags=to_list_str(row.get("tags")),
        source=to_optional_str(row.get("source")),
        meta=to_json_dict(row.get("meta")),
    )
