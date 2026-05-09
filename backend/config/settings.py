import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # PostgreSQL
    PG_DB: str = os.getenv("POSTGRES_DB", "Hackathon")
    PG_USER: str = os.getenv("POSTGRES_USER", "hackathon")
    PG_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    PG_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    PG_PORT: int = int(os.getenv("POSTGRES_PORT", "5433"))

    # Elasticsearch
    ES_URL: str = os.getenv("ELASTIC_URL", "http://localhost:9200")
    ES_INDEX: str = os.getenv("ELASTIC_INDEX", "hackathon-hybrid")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    VECTOR_DIMS: int = int(os.getenv("VECTOR_DIMS", "1536"))

    # Pipeline
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "64"))


settings = Settings()
