from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from config.settings import settings


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    def dsn(self) -> str:
        password = quote_plus(self.password)
        return f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}"


def load_postgres_config() -> PostgresConfig:
    return PostgresConfig(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        database=settings.PG_DB,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
    )


def create_connection(config: PostgresConfig | None = None) -> Connection[dict]:
    resolved = config or load_postgres_config()
    if resolved.host.startswith("/"):
        return psycopg.connect(
            dbname=resolved.database,
            user=resolved.user,
            password=resolved.password,
            host=resolved.host,
            port=resolved.port,
            row_factory=dict_row,
        )
    return psycopg.connect(resolved.dsn(), row_factory=dict_row)
