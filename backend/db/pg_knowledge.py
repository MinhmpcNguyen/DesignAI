from __future__ import annotations

from collections.abc import Sequence
import logging

from psycopg.types.json import Jsonb

from db.models import (
    DesignKnowledge,
    DesignKnowledgeEmbedding,
    DesignKnowledgeFilter,
    DesignKnowledgeId,
    TenantId,
)
from db.pg_utils import (
    ConnectionFactory,
    RowMapping,
    to_json_dict,
    to_list_str,
    to_optional_str,
    to_str,
    vector_literal,
)
from db.postgres import create_connection


class PostgresDesignKnowledgeRepository:
    def __init__(self, connection_factory: ConnectionFactory | None = None) -> None:
        self._connection_factory = connection_factory or create_connection

    def create_knowledge(self, knowledge: DesignKnowledge) -> None:
        query = """
            INSERT INTO design_knowledge (
                id,
                tenant_id,
                title,
                content,
                category,
                tags,
                source,
                meta
            )
            VALUES (
                %(id)s,
                %(tenant_id)s,
                %(title)s,
                %(content)s,
                %(category)s,
                %(tags)s,
                %(source)s,
                %(meta)s
            )
        """
        params = _knowledge_to_params(knowledge)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def upsert_knowledge(self, knowledge: DesignKnowledge) -> None:
        query = """
            INSERT INTO design_knowledge (
                id,
                tenant_id,
                title,
                content,
                category,
                tags,
                source,
                meta
            )
            VALUES (
                %(id)s,
                %(tenant_id)s,
                %(title)s,
                %(content)s,
                %(category)s,
                %(tags)s,
                %(source)s,
                %(meta)s
            )
            ON CONFLICT (id)
            DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                category = EXCLUDED.category,
                tags = EXCLUDED.tags,
                source = EXCLUDED.source,
                meta = EXCLUDED.meta,
                updated_at = NOW()
        """
        params = _knowledge_to_params(knowledge)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def update_knowledge(self, knowledge: DesignKnowledge) -> None:
        query = """
            UPDATE design_knowledge
            SET
                tenant_id = %(tenant_id)s,
                title = %(title)s,
                content = %(content)s,
                category = %(category)s,
                tags = %(tags)s,
                source = %(source)s,
                meta = %(meta)s,
                updated_at = NOW()
            WHERE id = %(id)s
        """
        params = _knowledge_to_params(knowledge)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def get_knowledge(self, knowledge_id: DesignKnowledgeId) -> DesignKnowledge | None:
        query = "SELECT * FROM design_knowledge WHERE id = %(id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"id": knowledge_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_knowledge(row)

    def list_knowledge(
        self, knowledge_filter: DesignKnowledgeFilter
    ) -> Sequence[DesignKnowledge]:
        query, params = _build_knowledge_filter_query(knowledge_filter)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [_row_to_knowledge(row) for row in rows]

    def upsert_knowledge_embedding(self, embedding: DesignKnowledgeEmbedding) -> None:
        query = """
            INSERT INTO design_knowledge_embeddings (
                knowledge_id,
                content,
                model,
                meta,
                vector
            )
            VALUES (
                %(knowledge_id)s,
                %(content)s,
                %(model)s,
                %(meta)s,
                %(vector)s::vector
            )
            ON CONFLICT (knowledge_id, model)
            DO UPDATE SET
                content = EXCLUDED.content,
                meta = EXCLUDED.meta,
                vector = EXCLUDED.vector,
                created_at = NOW()
        """
        params = {
            "knowledge_id": embedding.knowledge_id,
            "content": embedding.content,
            "model": embedding.model,
            "meta": Jsonb(embedding.meta),
            "vector": vector_literal(embedding.vector),
        }
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def search_knowledge_by_embedding(
        self,
        tenant_id: TenantId | None,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[DesignKnowledge]:
        logger = logging.getLogger("rag")
        query = """
            SELECT k.*
            FROM design_knowledge_embeddings e
            JOIN design_knowledge k ON k.id = e.knowledge_id
            WHERE (%(tenant_id)s::text IS NULL OR k.tenant_id = %(tenant_id)s::text)
            ORDER BY e.vector <-> %(vector)s::vector
            LIMIT %(limit)s
        """
        params = {
            "tenant_id": tenant_id,
            "vector": vector_literal(embedding),
            "limit": limit,
        }
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        logger.info("Knowledge search returned %d rows", len(rows))
        return [_row_to_knowledge(row) for row in rows]

    def list_embeddings(
        self, knowledge_ids: Sequence[DesignKnowledgeId]
    ) -> dict[DesignKnowledgeId, list[float]]:
        if not knowledge_ids:
            return {}
        query = """
            SELECT knowledge_id, vector::float4[] AS vector
            FROM design_knowledge_embeddings
            WHERE knowledge_id = ANY(%(ids)s::text[])
        """
        params = {"ids": list(knowledge_ids)}
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        results: dict[DesignKnowledgeId, list[float]] = {}
        for row in rows:
            knowledge_id = to_str(row.get("knowledge_id"))
            vector = row.get("vector") or []
            if isinstance(vector, list):
                results[knowledge_id] = [float(value) for value in vector]
        return results


def _knowledge_to_params(knowledge: DesignKnowledge) -> dict[str, object]:
    return {
        "id": knowledge.id,
        "tenant_id": knowledge.tenant_id,
        "title": knowledge.title,
        "content": knowledge.content,
        "category": knowledge.category,
        "tags": knowledge.tags,
        "source": knowledge.source,
        "meta": Jsonb(knowledge.meta),
    }


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
