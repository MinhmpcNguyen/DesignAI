from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.pipeline import router as pipeline_router
from config import root_config
from config.logging_config import setup_logging
from config.models import OpenAIModelGroupConfig
from config.openai_config import OpenAIConfig
from db.demo_data import ensure_demo_inventory_loaded
from db.runtime_init import ensure_runtime_schema

app = FastAPI(
    title="TKNT Normalize-Run API",
    version="1.0.0",
    description=(
        "Minimal FastAPI surface for `POST /pipeline/normalize-run`: "
        "normalize frontend room coordinates, run the layout pipeline, and return "
        "frontend-ready furniture objects."
    ),
)
logger = logging.getLogger(__name__)

DEFAULT_CORS_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "https://house-design-protocol.vercel.app",
)


def _csv_env_values(name: str) -> list[str]:
    raw_value = os.getenv(name, "")
    return [
        value.strip().rstrip("/") for value in raw_value.split(",") if value.strip()
    ]


def _cors_allowed_origins() -> list[str]:
    configured_origins = _csv_env_values("TKNT_CORS_ALLOWED_ORIGINS")
    if configured_origins:
        return configured_origins
    return list(DEFAULT_CORS_ALLOWED_ORIGINS)


def _cors_allowed_origin_regex() -> str | None:
    regex = os.getenv("TKNT_CORS_ALLOWED_ORIGIN_REGEX", "").strip()
    return regex or None


@app.on_event("startup")
def _startup_logging() -> None:
    # Ensure our internal logs (agents/RAG/search) show up when running via uvicorn.
    setup_logging()
    _initialize_runtime_schema()
    _log_runtime_profile()


def _initialize_runtime_schema() -> None:
    try:
        ensure_runtime_schema()
        loaded_count = ensure_demo_inventory_loaded()
        if loaded_count:
            logger.info("Loaded %d bundled demo inventory assets.", loaded_count)
    except Exception as exc:
        logger.exception("Runtime schema initialization skipped: %s", exc)


def _log_runtime_profile() -> None:
    gemini_config = root_config.services.gemini
    mistral_config = root_config.services.mistral
    ollama_config = root_config.services.ollama
    semantic_enabled = root_config.services.semantic_search.enabled
    logged_provider = False

    if mistral_config.enabled and mistral_config.models is not None:
        logger.info(
            "LLM provider: Mistral | base_url=%s | primary=%s | helper=%s",
            mistral_config.base_url,
            mistral_config.models.primary.name,
            mistral_config.models.helper.name,
        )
        logged_provider = True
    if ollama_config.enabled and ollama_config.models is not None:
        logger.info(
            "LLM provider: Ollama | base_url=%s | primary=%s | helper=%s",
            ollama_config.base_url,
            ollama_config.models.primary.name,
            ollama_config.models.helper.name,
        )
        logged_provider = True
    if gemini_config.enabled and gemini_config.models is not None:
        logger.info(
            "LLM provider: Gemini | base_url=%s | primary=%s | helper=%s",
            gemini_config.base_url,
            gemini_config.models.primary.name,
            gemini_config.models.helper.name,
        )
        logged_provider = True
    if not logged_provider and OpenAIConfig.IS_OPENAI_AZURE:
        primary_model, helper_model = _openai_model_names(OpenAIConfig.MODELS)
        logger.info(
            "LLM provider: Azure OpenAI | primary=%s | helper=%s",
            primary_model,
            helper_model,
        )
    elif not logged_provider:
        primary_model, helper_model = _openai_model_names(OpenAIConfig.MODELS)
        logger.info(
            "LLM provider: OpenAI-compatible API | primary=%s | helper=%s",
            primary_model,
            helper_model,
        )

    if semantic_enabled:
        logger.info("Knowledge retrieval: semantic search enabled.")
    else:
        logger.info(
            "Knowledge retrieval: semantic search disabled; "
            "lexical fallback search enabled."
        )


def _openai_model_names(models: OpenAIModelGroupConfig) -> tuple[str, str]:
    resolved_models = models.resolved_models()
    return (
        resolved_models["primary"].name,
        resolved_models["helper"].name,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router)


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok"}
