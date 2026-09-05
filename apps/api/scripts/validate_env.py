#!/usr/bin/env python3
"""
TRACE-X Environment Validation

Checks the current environment (.env / process env) for the config
Settings actually reads, without ever printing a secret's value - only
whether it is present, and what functionality is unavailable without it.

Usage:
    cd apps/api && python scripts/validate_env.py
    # or, against a specific env file:
    cd apps/api && python -c "from dotenv import load_dotenv; load_dotenv('../../docker/.env')" \
        && python scripts/validate_env.py

Exit code is 0 if every REQUIRED_FOR_CORE setting is present and valid,
1 otherwise (missing/placeholder secrets, or a production-only check
failing) - suitable for a pre-deploy CI/CD gate.
"""

import contextlib
import sys
from pathlib import Path

# Windows terminals often default stdout to a legacy codepage (cp1252) that
# can't encode the ✓/⚠/✗ markers below; UTF-8 output works in any modern
# terminal (including Windows Terminal / CI logs) that would otherwise crash.
with contextlib.suppress(AttributeError, ValueError):
    sys.stdout.reconfigure(encoding="utf-8")

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from pydantic import ValidationError  # noqa: E402

from src.core.config import Settings  # noqa: E402

OK = "✓"
WARN = "⚠"
FAIL = "✗"

# (env var, "what breaks without it")
OPTIONAL_PROVIDERS = [
    ("ANTHROPIC_API_KEY", "AI assistant runs in deterministic demo mode instead of live Claude"),
    ("ALCHEMY_API_KEY", "no Alchemy-backed chain data (Ethereum/Polygon/Arbitrum/Optimism/Base)"),
    ("INFURA_API_KEY", "no Infura-backed chain data (fallback if Alchemy is also unset)"),
    ("BSC_RPC_URL", "no BSC chain data"),
    ("CHAINALYSIS_API_KEY", "no Chainalysis entity/sanctions intelligence"),
    ("CIPHERTRACE_API_KEY", "no CipherTrace entity/sanctions intelligence"),
    ("OPENROUTER_API_KEY", "AI assistant uses OpenRouter instead of Anthropic when AI_PROVIDER=openrouter"),
    ("OPENROUTER_MODEL", "Required when using OpenRouter - specifies which model to use via OpenRouter"),
]


def main() -> int:
    print("TRACE-X Environment Validation\n")
    ok = True

    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        print(f"{FAIL} Settings failed to load - required configuration is missing or invalid:")
        for err in e.errors():
            field = ".".join(str(p) for p in err["loc"])
            print(f"    - {field}: {err['msg']}")
        print("\nSee .env.example / docker/.env.example for the required variables.")
        return 1

    def check(label: str, condition: bool, note: str = "") -> None:
        nonlocal ok
        mark = OK if condition else FAIL
        if not condition:
            ok = False
        suffix = f" ({note})" if note and not condition else ""
        print(f"{mark} {label}{suffix}")

    check("SECRET_KEY configured", bool(settings.SECRET_KEY) and len(settings.SECRET_KEY) >= 32)
    check(
        "DATABASE_URL configured",
        bool(settings.DATABASE_URL) and "tracex:tracex@localhost" not in settings.DATABASE_URL
        if settings.is_production
        else bool(settings.DATABASE_URL),
    )
    check("REDIS_URL configured", bool(settings.REDIS_URL))
    check("NEO4J_URI configured", bool(settings.NEO4J_URI))
    check(
        "NEO4J_PASSWORD configured",
        bool(settings.NEO4J_PASSWORD) and settings.NEO4J_PASSWORD != "tracexneo4j"
        if settings.is_production
        else bool(settings.NEO4J_PASSWORD),
        "still the dev default in production" if settings.is_production else "",
    )

    print()
    for var, impact in OPTIONAL_PROVIDERS:
        present = bool(getattr(settings, var))
        mark = OK if present else WARN
        suffix = "configured" if present else f"not configured - {impact}"
        print(f"{mark} {var} {suffix}")

    print()
    mode = settings.effective_ai_mode
    print(f"{OK if mode != 'disabled' else WARN} AI mode: {mode}")
    if mode == "demo":
        print(f"{OK} Demo fallback enabled (deterministic, evidence-grounded)")

    # Validate AI_PROVIDER and required variables
    provider = settings.AI_PROVIDER
    if mode == "live":
        if provider == "openrouter":
            # OpenRouter is required when AI_PROVIDER=openrouter in live mode
            openrouter_api_key = bool(settings.OPENROUTER_API_KEY)
            openrouter_model = bool(settings.OPENROUTER_MODEL)

            check("OPENROUTER_API_KEY configured", openrouter_api_key)
            check("OPENROUTER_MODEL configured", openrouter_model)

            if not openrouter_api_key or not openrouter_model:
                ok = False
        elif provider != "anthropic":
            # Warn if provider is neither anthropic nor openrouter
            print(f"{WARN} AI_PROVIDER set to '{provider}' - only 'anthropic' and 'openrouter' are supported")

    if settings.is_production:
        print()
        default_cors = ["http://localhost:3000", "http://127.0.0.1:3000"]
        check(
            "CORS_ORIGINS overridden from dev default",
            default_cors != settings.CORS_ORIGINS,
            "still the localhost dev default - real frontend origin will be blocked",
        )

    print(
        f"\n{'PASSED' if ok else 'FAILED'} - see docs/EXTERNAL_SERVICES_SETUP.md for setup steps."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
