from __future__ import annotations

from collections.abc import Sequence
import logging

from psycopg.types.json import Jsonb

from db.models import (
    Asset,
    AssetDimensions,
    AssetEmbedding,
    AssetFile,
    AssetFilter,
    AssetId,
    AssetPrice,
    TenantId,
)
from db.pg_utils import (
    ConnectionFactory,
    RowMapping,
    to_json_dict,
    to_list_str,
    to_optional_float,
    to_optional_int,
    to_optional_str,
    to_str,
    vector_literal,
)
from db.postgres import create_connection


class PostgresAssetRepository:
    def __init__(self, connection_factory: ConnectionFactory | None = None) -> None:
        self._connection_factory = connection_factory or create_connection

    def create_asset(self, asset: Asset) -> None:
        query = """
            INSERT INTO assets (
                id,
                tenant_id,
                type,
                name,
                style_tags,
                material,
                brand,
                length_mm,
                width_mm,
                height_mm,
                price_amount,
                price_currency,
                attributes
            )
            VALUES (
                %(id)s,
                %(tenant_id)s,
                %(type)s,
                %(name)s,
                %(style_tags)s,
                %(material)s,
                %(brand)s,
                %(length_mm)s,
                %(width_mm)s,
                %(height_mm)s,
                %(price_amount)s,
                %(price_currency)s,
                %(attributes)s
            )
        """
        params = _asset_to_params(asset)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def upsert_asset(self, asset: Asset) -> None:
        query = """
            INSERT INTO assets (
                id,
                tenant_id,
                type,
                name,
                style_tags,
                material,
                brand,
                length_mm,
                width_mm,
                height_mm,
                price_amount,
                price_currency,
                attributes
            )
            VALUES (
                %(id)s,
                %(tenant_id)s,
                %(type)s,
                %(name)s,
                %(style_tags)s,
                %(material)s,
                %(brand)s,
                %(length_mm)s,
                %(width_mm)s,
                %(height_mm)s,
                %(price_amount)s,
                %(price_currency)s,
                %(attributes)s
            )
            ON CONFLICT (id)
            DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                type = EXCLUDED.type,
                name = EXCLUDED.name,
                style_tags = EXCLUDED.style_tags,
                material = EXCLUDED.material,
                brand = EXCLUDED.brand,
                length_mm = EXCLUDED.length_mm,
                width_mm = EXCLUDED.width_mm,
                height_mm = EXCLUDED.height_mm,
                price_amount = EXCLUDED.price_amount,
                price_currency = EXCLUDED.price_currency,
                attributes = EXCLUDED.attributes,
                updated_at = NOW()
        """
        params = _asset_to_params(asset)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def update_asset(self, asset: Asset) -> None:
        query = """
            UPDATE assets
            SET
                tenant_id = %(tenant_id)s,
                type = %(type)s,
                name = %(name)s,
                style_tags = %(style_tags)s,
                material = %(material)s,
                brand = %(brand)s,
                length_mm = %(length_mm)s,
                width_mm = %(width_mm)s,
                height_mm = %(height_mm)s,
                price_amount = %(price_amount)s,
                price_currency = %(price_currency)s,
                attributes = %(attributes)s,
                updated_at = NOW()
            WHERE id = %(id)s
        """
        params = _asset_to_params(asset)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def get_asset(self, asset_id: AssetId) -> Asset | None:
        query = "SELECT * FROM assets WHERE id = %(id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"id": asset_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_asset(row)

    def list_assets(self, asset_filter: AssetFilter) -> Sequence[Asset]:
        query, params = _build_asset_filter_query(asset_filter)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [_row_to_asset(row) for row in rows]

    def create_asset_file(self, asset_file: AssetFile) -> None:
        query = """
            INSERT INTO asset_files (
                id,
                asset_id,
                file_kind,
                provider,
                storage_key,
                mime,
                width_px,
                height_px,
                bytes_size,
                role,
                meta
            )
            VALUES (
                %(id)s,
                %(asset_id)s,
                %(file_kind)s,
                %(provider)s,
                %(storage_key)s,
                %(mime)s,
                %(width_px)s,
                %(height_px)s,
                %(bytes_size)s,
                %(role)s,
                %(meta)s
            )
        """
        params = _asset_file_to_params(asset_file)
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def list_asset_files(self, asset_id: AssetId) -> Sequence[AssetFile]:
        query = "SELECT * FROM asset_files WHERE asset_id = %(asset_id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"asset_id": asset_id})
                rows = cur.fetchall()
        return [_row_to_asset_file(row) for row in rows]

    def get_asset_file(self, asset_file_id: str) -> AssetFile | None:
        query = "SELECT * FROM asset_files WHERE id = %(asset_file_id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"asset_file_id": asset_file_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_asset_file(row)

    def upsert_embedding(self, embedding: AssetEmbedding) -> None:
        query = """
            INSERT INTO asset_embeddings (
                asset_id,
                content,
                model,
                meta,
                vector
            )
            VALUES (
                %(asset_id)s,
                %(content)s,
                %(model)s,
                %(meta)s,
                %(vector)s::vector
            )
            ON CONFLICT (asset_id, model)
            DO UPDATE SET
                content = EXCLUDED.content,
                meta = EXCLUDED.meta,
                vector = EXCLUDED.vector,
                created_at = NOW()
        """
        params = {
            "asset_id": embedding.asset_id,
            "content": embedding.content,
            "model": embedding.model,
            "meta": Jsonb(embedding.meta),
            "vector": vector_literal(embedding.vector),
        }
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def search_by_embedding(
        self,
        tenant_id: TenantId,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[Asset]:
        logger = logging.getLogger("rag")
        query = """
            SELECT a.*
            FROM asset_embeddings e
            JOIN assets a ON a.id = e.asset_id
            WHERE a.tenant_id = %(tenant_id)s
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
        logger.info("Asset search returned %d rows", len(rows))
        return [_row_to_asset(row) for row in rows]


def _asset_to_params(asset: Asset) -> dict[str, object]:
    dimensions = asset.dimensions or AssetDimensions()
    return {
        "id": asset.id,
        "tenant_id": asset.tenant_id,
        "type": asset.type,
        "name": asset.name,
        "style_tags": asset.style_tags,
        "material": asset.material,
        "brand": asset.brand,
        "length_mm": dimensions.length_mm,
        "width_mm": dimensions.width_mm,
        "height_mm": dimensions.height_mm,
        "price_amount": asset.price.amount if asset.price else None,
        "price_currency": asset.price.currency if asset.price else None,
        "attributes": Jsonb(asset.attributes),
    }


def _asset_file_to_params(asset_file: AssetFile) -> dict[str, object]:
    return {
        "id": asset_file.id,
        "asset_id": asset_file.asset_id,
        "file_kind": asset_file.file_kind,
        "provider": asset_file.provider,
        "storage_key": asset_file.storage_key,
        "mime": asset_file.mime,
        "width_px": asset_file.width_px,
        "height_px": asset_file.height_px,
        "bytes_size": asset_file.bytes_size,
        "role": asset_file.role,
        "meta": Jsonb(asset_file.meta),
    }


def _build_asset_filter_query(
    asset_filter: AssetFilter,
) -> tuple[str, dict[str, object]]:
    clauses = ["tenant_id = %(tenant_id)s"]
    params: dict[str, object] = {"tenant_id": asset_filter.tenant_id}

    if asset_filter.type:
        clauses.append("type = %(type)s")
        params["type"] = asset_filter.type
    if asset_filter.material:
        clauses.append("material = %(material)s")
        params["material"] = asset_filter.material
    if asset_filter.brand:
        clauses.append("brand = %(brand)s")
        params["brand"] = asset_filter.brand
    if asset_filter.style_tags:
        clauses.append("style_tags @> %(style_tags)s::text[]")
        params["style_tags"] = asset_filter.style_tags
    if asset_filter.price_min is not None:
        clauses.append("price_amount >= %(price_min)s")
        params["price_min"] = asset_filter.price_min
    if asset_filter.price_max is not None:
        clauses.append("price_amount <= %(price_max)s")
        params["price_max"] = asset_filter.price_max
    if asset_filter.attributes:
        clauses.append("attributes @> %(attributes)s::jsonb")
        params["attributes"] = Jsonb(dict(asset_filter.attributes))

    where_clause = " AND ".join(clauses)
    query = f"SELECT * FROM assets WHERE {where_clause}"
    return query, params


def _row_to_asset(row: RowMapping) -> Asset:
    dimensions = _row_to_dimensions(row)
    price = _row_to_price(row)
    return Asset(
        id=to_str(row.get("id")),
        tenant_id=to_str(row.get("tenant_id")),
        type=to_str(row.get("type")),
        name=to_str(row.get("name")),
        style_tags=to_list_str(row.get("style_tags")),
        material=to_optional_str(row.get("material")),
        brand=to_optional_str(row.get("brand")),
        dimensions=dimensions,
        price=price,
        attributes=to_json_dict(row.get("attributes")),
    )


def _row_to_asset_file(row: RowMapping) -> AssetFile:
    return AssetFile(
        id=to_str(row.get("id")),
        asset_id=to_str(row.get("asset_id")),
        file_kind=to_str(row.get("file_kind")),
        provider=to_str(row.get("provider")),
        storage_key=to_str(row.get("storage_key")),
        mime=to_optional_str(row.get("mime")),
        width_px=to_optional_int(row.get("width_px")),
        height_px=to_optional_int(row.get("height_px")),
        bytes_size=to_optional_int(row.get("bytes_size")),
        role=to_optional_str(row.get("role")),
        meta=to_json_dict(row.get("meta")),
    )


def _row_to_dimensions(row: RowMapping) -> AssetDimensions | None:
    length_mm = to_optional_float(row.get("length_mm"))
    width_mm = to_optional_float(row.get("width_mm"))
    height_mm = to_optional_float(row.get("height_mm"))
    if length_mm is None and width_mm is None and height_mm is None:
        return None
    return AssetDimensions(length_mm=length_mm, width_mm=width_mm, height_mm=height_mm)


def _row_to_price(row: RowMapping) -> AssetPrice | None:
    amount = to_optional_float(row.get("price_amount"))
    currency = to_optional_str(row.get("price_currency"))
    if amount is None:
        if currency is None:
            return None
        raise ValueError("price_amount is required when price_currency is set.")
    return AssetPrice(amount=amount, currency=currency or "VND")
