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


settings = Settings()
