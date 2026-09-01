from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # --- WS1 auth hardening: SECRET_KEY block ---
    # No runtime-generated fallback. A freshly generated key on every process
    # start silently invalidates all previously issued JWTs across restarts
    # and breaks multi-worker deploys (each worker would mint a different
    # key). SECRET_KEY MUST come from the environment / .env file.
    SECRET_KEY: str
    # --- end SECRET_KEY block ---
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
    ARBITRUM_RPC_URL: str | None = None
    OPTIMISM_RPC_URL: str | None = None
    BASE_RPC_URL: str | None = None

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

    # --- WS1 auth hardening: startup validation block ---
    @model_validator(mode="after")
    def _validate_production_requirements(self) -> "Settings":
        """Fail fast at startup instead of running an insecure production deploy.

        SECRET_KEY is already required with no default (pydantic-settings
        raises before we even get here if it's unset in any environment).
        This validator adds the production-specific checks: SECRET_KEY must
        be a strong value (not a short/placeholder string) and DATABASE_URL
        must not be left pointing at the local-dev default.
        """
        if self.APP_ENV == "production":
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong value (>=32 chars) "
                    "via environment variables when APP_ENV=production."
                )
            if not self.DATABASE_URL or "tracex:tracex@localhost" in self.DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL must be explicitly configured (not the "
                    "local-dev default) via environment variables when "
                    "APP_ENV=production."
                )
        return self

    # --- end startup validation block ---

    # --- WS3: provider-key validation (appended, do not merge into unrelated blocks) ---
    @property
    def configured_blockchain_providers(self) -> list[str]:
        """Blockchain (chain-data) providers with an API key present."""
        providers = []
        if self.ALCHEMY_API_KEY:
            providers.append("alchemy")
        if self.INFURA_API_KEY:
            providers.append("infura")
        return providers

    @property
    def configured_intel_providers(self) -> list[str]:
        """Entity-intelligence providers (Chainalysis/CipherTrace) with an API key present."""
        providers = []
        if self.CHAINALYSIS_API_KEY:
            providers.append("chainalysis")
        if self.CIPHERTRACE_API_KEY:
            providers.append("ciphertrace")
        return providers

    # --- end WS3 block ---


@lru_cache
def get_settings() -> Settings:
    # SECRET_KEY (and other required fields) come from the environment/.env
    # file at runtime via pydantic-settings, not from a literal call argument
    # -- mypy has no way to see that, hence the ignore.
    return Settings()  # type: ignore[call-arg]
