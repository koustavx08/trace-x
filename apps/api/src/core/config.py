from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# .env discovery must not depend on the current working directory: the API is
# started from the repo root (pytest), from apps/api (uvicorn/alembic) and from
# /app (Docker). Resolve the candidate locations absolutely, from this file.
#
# This file is <api_dir>/src/core/config.py, so parents[2] is the api dir. In a
# source checkout the repo root is two levels above that (<repo>/apps/api), but
# in the container the api dir is mounted at /app and those levels do not
# exist -- indexing blindly would raise IndexError at import time and take the
# whole app down. Hence the guarded lookup below.
#
# Later entries win, so an api-dir .env overrides the repo-root one; real
# environment variables (what Docker Compose sets) still beat both.
def _env_file_candidates() -> tuple[Path, ...]:
    parents = Path(__file__).resolve().parents
    api_dir = parents[2]
    candidates = []
    if len(parents) > 4:  # source checkout: <repo>/apps/api/src/core/config.py
        candidates.append(parents[4] / ".env")
    candidates.append(api_dir / ".env")
    return tuple(candidates)


_ENV_FILES = _env_file_candidates()

#: Development/CI SECRET_KEY values that are committed to this repo. They are
#: fine for local work but must never sign tokens in production, so
#: `_validate_production_requirements` rejects them outright.
_PLACEHOLDER_SECRET_KEYS = frozenset(
    {
        "trace-x-super-secret-key-change-in-production",
        "dev-secret-key-not-for-production-use-only-min-32-chars",
        "ci-test-secret-key-not-for-production-use-only-min-32-chars",
        "your-secret-key-min-32-chars",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
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
    # No default, and no runtime-generated fallback. A hardcoded default is a
    # published signing key (anyone can mint an admin JWT); a freshly generated
    # one per process silently invalidates all previously issued JWTs across
    # restarts and breaks multi-worker deploys. SECRET_KEY MUST come from the
    # environment or a .env file -- pydantic-settings reads both, so no
    # explicit os.environ lookup is needed here.
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
    # Neither Alchemy nor Infura support BSC; there's no vendor API key for
    # it, only a plain JSON-RPC endpoint (e.g. a public node or a BSC-
    # specific RPC provider like Ankr/QuickNode/Chainstack).
    BSC_RPC_URL: str | None = None

    # Entity Intelligence
    CHAINALYSIS_API_KEY: str | None = None
    CIPHERTRACE_API_KEY: str | None = None
    # treasury.gov/ofac/downloads/sdn.csv now only 302s here; point at the
    # current endpoint directly (it still redirects once more, to a signed
    # S3 URL -- see the follow_redirects note in intelligence/entities.py).
    OFAC_SDN_LIST_URL: str = (
        "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/sdn.csv"
    )

    # --- WS2: AI Integration -----------------------------------
    # AI_MODE: live | demo | disabled. Leave unset to auto-select "live" when
    # ANTHROPIC_API_KEY is present, else "demo". Set "demo" to force the
    # deterministic template mode even with a key configured (e.g. for a
    # reliable offline demo), or "disabled" to turn off the AI assistant
    # entirely (the rest of the platform is unaffected either way).
    AI_MODE: str | None = None
    # AI_PROVIDER: anthropic | openrouter. Only used when AI_MODE=live.
    # Leave unset to default to "anthropic" for backward compatibility.
    AI_PROVIDER: str | None = None
    # Anthropic configuration
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    # OpenRouter configuration
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str | None = None
    # ----------------------------------------------------------------------

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def uses_secure_cookies(self) -> bool:
        """Whether auth cookies should carry the `Secure` flag.

        `Secure` cookies are only ever sent back over HTTPS. Local development
        and the test suite (CI sets APP_ENV=test) both run over plain HTTP, so
        flagging them there means the browser/test client silently drops the
        cookie and every cookie-authenticated request 401s.
        """
        return not (self.is_development or self.is_test)

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
            # Length alone is not enough: the dev/compose placeholders below are
            # both >=32 chars and are published in this repo, so a production
            # deploy that forgot to override SECRET_KEY would otherwise boot
            # with a signing key anyone can read off GitHub.
            if self.SECRET_KEY in _PLACEHOLDER_SECRET_KEYS:
                raise ValueError(
                    "SECRET_KEY is still set to a well-known development "
                    "placeholder. Generate a unique value (e.g. "
                    '`python -c "import secrets; print(secrets.token_urlsafe(48))"`) '
                    "and set it via environment variables when APP_ENV=production."
                )
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

    @property
    def effective_ai_mode(self) -> str:
        """Resolves AI_MODE to one of "live" / "demo" / "disabled".

        A "live" request with no API key for the selected provider degrades to "demo" rather
        than erroring - there's nothing to call live with, but the assistant
        should still answer from deterministic templates over real evidence
        instead of refusing outright.
        """
        # Which provider a "live" mode would actually call. Any value other
        # than "openrouter" (including unset) means Anthropic.
        provider = self.AI_PROVIDER or "anthropic"
        provider_key = (
            self.OPENROUTER_API_KEY if provider == "openrouter" else self.ANTHROPIC_API_KEY
        )

        mode = self.AI_MODE if self.AI_MODE in ("live", "demo", "disabled") else None
        # Auto-select keys off the *selected* provider's key, not Anthropic's:
        # AI_PROVIDER=openrouter with only OPENROUTER_API_KEY set is a valid
        # live configuration and must not silently resolve to "demo".
        mode = mode or ("live" if provider_key else "demo")
        if mode == "live" and not provider_key:
            return "demo"
        return mode


@lru_cache
def get_settings() -> Settings:
    # SECRET_KEY (and other required fields) come from the environment/.env
    # file at runtime via pydantic-settings, not from a literal call argument
    # -- mypy has no way to see that, hence the ignore.
    return Settings()  # type: ignore[call-arg]
