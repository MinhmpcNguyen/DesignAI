from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from db.models import (
    Asset,
    AssetEmbedding,
    AssetFile,
    AssetFilter,
    AssetId,
    DesignKnowledge,
    DesignKnowledgeEmbedding,
    DesignKnowledgeFilter,
    DesignKnowledgeId,
    TenantId,
)


class AssetRepository(Protocol):
    def create_asset(self, asset: Asset) -> None: ...

    def update_asset(self, asset: Asset) -> None: ...

    def get_asset(self, asset_id: AssetId) -> Asset | None: ...

    def list_assets(self, asset_filter: AssetFilter) -> Sequence[Asset]: ...

    def create_asset_file(self, asset_file: AssetFile) -> None: ...

    def list_asset_files(self, asset_id: AssetId) -> Sequence[AssetFile]: ...

    def upsert_embedding(self, embedding: AssetEmbedding) -> None: ...

    def search_by_embedding(
        self,
        tenant_id: TenantId,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[Asset]: ...


class InMemoryAssetRepository:
    def __init__(self) -> None:
        self._assets: dict[AssetId, Asset] = {}
        self._asset_files: dict[AssetId, list[AssetFile]] = {}
        self._embeddings: dict[AssetId, AssetEmbedding] = {}

    def create_asset(self, asset: Asset) -> None:
        self._assets[asset.id] = asset

    def update_asset(self, asset: Asset) -> None:
        self._assets[asset.id] = asset

    def get_asset(self, asset_id: AssetId) -> Asset | None:
        return self._assets.get(asset_id)

    def list_assets(self, asset_filter: AssetFilter) -> Sequence[Asset]:
        results: list[Asset] = []
        for asset in self._assets.values():
            if asset.tenant_id != asset_filter.tenant_id:
                continue
            if asset_filter.type and asset.type != asset_filter.type:
                continue
            if asset_filter.material and asset.material != asset_filter.material:
                continue
            if asset_filter.brand and asset.brand != asset_filter.brand:
                continue
            if asset_filter.style_tags:
                if not set(asset_filter.style_tags).issubset(asset.style_tags):
                    continue
            results.append(asset)
        return results

    def create_asset_file(self, asset_file: AssetFile) -> None:
        self._asset_files.setdefault(asset_file.asset_id, []).append(asset_file)

    def list_asset_files(self, asset_id: AssetId) -> Sequence[AssetFile]:
        return list(self._asset_files.get(asset_id, []))

    def upsert_embedding(self, embedding: AssetEmbedding) -> None:
        self._embeddings[embedding.asset_id] = embedding

    def search_by_embedding(
        self,
        tenant_id: TenantId,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[Asset]:
        _ = embedding
        results = [asset for asset in self._assets.values() if asset.tenant_id == tenant_id]
        return results[:limit]


class DesignKnowledgeRepository(Protocol):
    def create_knowledge(self, knowledge: DesignKnowledge) -> None: ...

    def update_knowledge(self, knowledge: DesignKnowledge) -> None: ...

    def get_knowledge(self, knowledge_id: DesignKnowledgeId) -> DesignKnowledge | None: ...

    def list_knowledge(
        self, knowledge_filter: DesignKnowledgeFilter
    ) -> Sequence[DesignKnowledge]: ...

    def upsert_knowledge_embedding(
        self, embedding: DesignKnowledgeEmbedding
    ) -> None: ...

    def search_knowledge_by_embedding(
        self,
        tenant_id: TenantId | None,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[DesignKnowledge]: ...

    def list_embeddings(
        self, knowledge_ids: Sequence[DesignKnowledgeId]
    ) -> dict[DesignKnowledgeId, list[float]]: ...


class InMemoryDesignKnowledgeRepository:
    def __init__(self) -> None:
        self._knowledge: dict[DesignKnowledgeId, DesignKnowledge] = {}
        self._embeddings: dict[DesignKnowledgeId, DesignKnowledgeEmbedding] = {}

    def create_knowledge(self, knowledge: DesignKnowledge) -> None:
        self._knowledge[knowledge.id] = knowledge

    def update_knowledge(self, knowledge: DesignKnowledge) -> None:
        self._knowledge[knowledge.id] = knowledge

    def get_knowledge(self, knowledge_id: DesignKnowledgeId) -> DesignKnowledge | None:
        return self._knowledge.get(knowledge_id)

    def list_knowledge(
        self, knowledge_filter: DesignKnowledgeFilter
    ) -> Sequence[DesignKnowledge]:
        results: list[DesignKnowledge] = []
        for item in self._knowledge.values():
            if knowledge_filter.tenant_id is not None:
                if item.tenant_id != knowledge_filter.tenant_id:
                    continue
            if knowledge_filter.category and item.category != knowledge_filter.category:
                continue
            if knowledge_filter.source and item.source != knowledge_filter.source:
                continue
            if knowledge_filter.tags:
                if not set(knowledge_filter.tags).issubset(item.tags):
                    continue
            results.append(item)
        return results

    def upsert_knowledge_embedding(self, embedding: DesignKnowledgeEmbedding) -> None:
        self._embeddings[embedding.knowledge_id] = embedding

    def search_knowledge_by_embedding(
        self,
        tenant_id: TenantId | None,
        embedding: Sequence[float],
        limit: int = 10,
    ) -> Sequence[DesignKnowledge]:
        _ = embedding
        if tenant_id is None:
            results = list(self._knowledge.values())
        else:
            results = [item for item in self._knowledge.values() if item.tenant_id == tenant_id]
        return results[:limit]

    def list_embeddings(
        self, knowledge_ids: Sequence[DesignKnowledgeId]
    ) -> dict[DesignKnowledgeId, list[float]]:
        results: dict[DesignKnowledgeId, list[float]] = {}
        for knowledge_id in knowledge_ids:
            embedding = self._embeddings.get(knowledge_id)
            if embedding is None:
                continue
            results[knowledge_id] = list(embedding.vector)
        return results
