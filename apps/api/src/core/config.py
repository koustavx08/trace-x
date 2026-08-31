from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "TRACE-X"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = secrets.token_urlsafe(32)
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tracex:tracex@localhost:5432/tracex"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "tracexneo4j"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Blockchain Providers
    ALCHEMY_API_KEY: str | None = None
    INFURA_API_KEY: str | None = None
    INFURA_API_SECRET: str | None = None
    ETHEREUM_RPC_URL: str | None = None
    POLYGON_RPC_URL: str | None = None

    # Entity Intelligence
    CHAINALYSIS_API_KEY: str | None = None
    CIPHERTRACE_API_KEY: str | None = None
    OFAC_SDN_LIST_URL: str = "https://www.treasury.gov/ofac/downloads/sdn.csv"

    # --- WS2: AI / Claude Integration -----------------------------------
    # When ANTHROPIC_API_KEY is unset, src/ai/service.py falls back to its
    # deterministic template/regex logic instead of calling the Anthropic API.
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    # ----------------------------------------------------------------------

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()