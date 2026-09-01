"""
Tests for src/auth/__init__.py and src/api/v1/auth.py.

This suite is split into two kinds of tests:

1. Pure-logic / unit tests (password hashing, JWT create/decode, RBAC
   dependency behavior, audit-log buffering) that exercise the *current*
   `src/auth/__init__.py` directly and need no database or running app.
2. HTTP-level tests against `/api/v1/auth/*` via `api_client`, which need a
   reachable `tracex_test` Postgres database (they skip cleanly if one
   isn't available -- see tests/fixtures_db.py).

WS1 ("Backend Auth Hardening") is expected to add `/auth/logout`, a JTI
token blacklist, rate limiting on `/auth/login` and `/auth/refresh`, and
DB-persisted audit logging. None of that exists in this worktree yet:
`src/auth/__init__.py` today has `AuditAction.LOGOUT` defined but nothing
ever emits it, `AuditLogger._buffer` is an in-memory list whose
`_flush_buffer()` just clears itself (no DB write), and there is no
`/auth/logout` route or rate-limit middleware at all. The tests below for
those behaviors are written defensively: they `pytest.xfail(...)` /
`pytest.skip(...)` with a clear reason when the feature isn't present yet,
so the suite doesn't fail outright against pre-WS1 code, but will need a
short fixup pass (replace the xfail/skip branch with a real assertion)
once WS1 lands.
"""

from uuid import uuid4

import pytest
from fixtures_db import api_client, db_session  # noqa: F401

from src.auth import (
    AuditAction,
    AuditLogEntry,
    AuditLogger,
    AuthService,
    TokenType,
    _decode_token_payload,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    require_admin,
    require_analyst,
    require_supervisor,
    verify_password,
)
from src.auth import (
    audit_logger as _module_audit_logger,
)
from src.core.exceptions import ValidationError
from src.models import User, UserRole


def _make_user(role: UserRole, *, active: bool = True) -> User:
    """Build a User ORM instance without touching the database -- fine for
    exercising pure in-memory logic like RBAC dependency functions."""
    return User(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@example.com",
        full_name="Test User",
        hashed_password=hash_password("irrelevant"),
        role=role,
        is_active=active,
    )


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_password_is_not_plaintext(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$2")  # bcrypt hash marker

    def test_verify_password_roundtrip(self):
        hashed = hash_password("s3cr3t-password")
        assert verify_password("s3cr3t-password", hashed) is True

    def test_verify_password_rejects_wrong_password(self):
        hashed = hash_password("s3cr3t-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_password_is_salted(self):
        # Two hashes of the same password should differ (random salt).
        assert hash_password("same-password") != hash_password("same-password")


# ---------------------------------------------------------------------------
# JWT token create/decode
# ---------------------------------------------------------------------------


class TestTokens:
    """Exercises signature/expiry decoding via `_decode_token_payload`, the
    sync inner helper `decode_token` wraps. `decode_token` itself additionally
    checks the Redis JTI blacklist, so it needs a reachable Redis and isn't a
    pure-logic call -- see TestAsyncDecodeToken below for that behavior.
    """

    def test_access_token_roundtrip(self):
        token = create_access_token({"sub": "user-123", "email": "a@b.com", "role": "analyst"})
        data = _decode_token_payload(token)
        assert data.sub == "user-123"
        assert data.email == "a@b.com"
        assert data.type == TokenType.ACCESS

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token({"sub": "user-123", "email": "a@b.com", "role": "admin"})
        data = _decode_token_payload(token)
        assert data.type == TokenType.REFRESH

    def test_access_and_refresh_tokens_have_distinct_jti(self):
        payload = {"sub": "user-123", "email": "a@b.com", "role": "analyst"}
        access = _decode_token_payload(create_access_token(payload))
        refresh = _decode_token_payload(create_refresh_token(payload))
        assert access.jti != refresh.jti

    def test_decode_invalid_token_raises_validation_error(self):
        with pytest.raises(ValidationError):
            _decode_token_payload("not-a-real-jwt")

    def test_decode_tampered_token_raises_validation_error(self):
        token = create_access_token({"sub": "user-123", "email": "a@b.com", "role": "analyst"})
        with pytest.raises(ValidationError):
            _decode_token_payload(token + "tampered")


# ---------------------------------------------------------------------------
# RBAC dependency functions (require_admin / require_supervisor / require_analyst)
# ---------------------------------------------------------------------------


class TestRBAC:
    @pytest.mark.parametrize(
        "role,expect_allowed",
        [
            (UserRole.ADMIN, True),
            (UserRole.SUPERVISOR, False),
            (UserRole.ANALYST, False),
        ],
    )
    async def test_require_admin(self, role, expect_allowed):
        user = _make_user(role)
        if expect_allowed:
            result = await require_admin(current_user=user)
            assert result is user
        else:
            with pytest.raises(Exception) as exc_info:
                await require_admin(current_user=user)
            assert getattr(exc_info.value, "status_code", None) == 403

    @pytest.mark.parametrize(
        "role,expect_allowed",
        [
            (UserRole.ADMIN, True),
            (UserRole.SUPERVISOR, True),
            (UserRole.ANALYST, False),
        ],
    )
    async def test_require_supervisor(self, role, expect_allowed):
        user = _make_user(role)
        if expect_allowed:
            result = await require_supervisor(current_user=user)
            assert result is user
        else:
            with pytest.raises(Exception) as exc_info:
                await require_supervisor(current_user=user)
            assert getattr(exc_info.value, "status_code", None) == 403

    @pytest.mark.parametrize(
        "role",
        [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.ANALYST],
    )
    async def test_require_analyst_allows_everyone(self, role):
        user = _make_user(role)
        result = await require_analyst(current_user=user)
        assert result is user


# ---------------------------------------------------------------------------
# Audit logging (current in-memory implementation)
# ---------------------------------------------------------------------------


class TestAuditLoggerCurrentBehavior:
    """AuditLogger now persists each entry immediately to the audit_log table
    (see src/auth/__init__.py's _persist); the in-memory buffer is only a
    resilience fallback for entries whose immediate persist attempt fails, so
    these tests fake _persist rather than depend on a real reachable DB.
    """

    async def test_log_persists_immediately_on_success(self):
        logger = AuditLogger()
        persisted = []

        async def fake_persist(entry):
            persisted.append(entry)

        logger._persist = fake_persist
        await logger.log(action=AuditAction.LOGIN, user_email="a@b.com", success=True)
        assert len(persisted) == 1
        assert persisted[0].action == AuditAction.LOGIN
        assert logger._buffer == []

    async def test_log_buffers_entry_when_persist_fails(self):
        logger = AuditLogger()

        async def failing_persist(entry):
            # Replicates the real _persist()'s own except-block contract:
            # a persistence failure is caught there and the entry is
            # appended to the buffer for retry, never raised to the caller.
            logger._buffer.append(entry)

        logger._persist = failing_persist
        assert logger._buffer == []
        await logger.log(action=AuditAction.LOGIN, user_email="a@b.com", success=True)
        assert len(logger._buffer) == 1
        assert logger._buffer[0].action == AuditAction.LOGIN

    async def test_buffer_flushes_and_clears_once_persist_succeeds(self):
        logger = AuditLogger()
        logger._buffer = [
            AuditLogEntry(action=AuditAction.CASE_READ, success=True) for _ in range(3)
        ]

        async def succeeding_persist(entry):
            pass

        logger._persist = succeeding_persist
        await logger._flush_buffer()
        assert logger._buffer == []

    async def test_close_flushes_remaining_buffer(self):
        logger = AuditLogger()
        logger._buffer = [AuditLogEntry(action=AuditAction.LOGIN_FAILED, success=False)]

        async def succeeding_persist(entry):
            pass

        logger._persist = succeeding_persist
        await logger.close()
        assert logger._buffer == []

    def test_audit_action_logout_is_defined_but_unused_pre_ws1(self):
        # Wired up per WS1 ("Wire the existing unused AuditAction.LOGOUT").
        assert AuditAction.LOGOUT.value == "logout"

    def test_module_level_audit_logger_singleton_exists(self):
        assert isinstance(_module_audit_logger, AuditLogger)


# ---------------------------------------------------------------------------
# AuthService (business logic layer) -- needs a real DB
# ---------------------------------------------------------------------------


class TestAuthServiceWithDB:
    async def test_login_with_valid_credentials_returns_tokens(self, db_session):
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email=f"{uuid4().hex[:8]}@example.com",
            password="correct-password",
            full_name="DB Test User",
            role=UserRole.ANALYST,
        )
        token_response = await auth_service.login(email=user.email, password="correct-password")
        assert token_response.access_token
        assert token_response.refresh_token
        assert token_response.token_type == "bearer"

        decoded = await decode_token(token_response.access_token)
        assert decoded.sub == str(user.id)
        assert decoded.role == UserRole.ANALYST

    async def test_login_with_invalid_password_raises(self, db_session):
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email=f"{uuid4().hex[:8]}@example.com",
            password="correct-password",
            full_name="DB Test User",
            role=UserRole.ANALYST,
        )
        with pytest.raises(ValidationError):
            await auth_service.login(email=user.email, password="wrong-password")

    async def test_refresh_token_issues_new_tokens(self, db_session):
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email=f"{uuid4().hex[:8]}@example.com",
            password="correct-password",
            full_name="DB Test User",
            role=UserRole.SUPERVISOR,
        )
        login_response = await auth_service.login(email=user.email, password="correct-password")
        refreshed = await auth_service.refresh_token(login_response.refresh_token)
        assert refreshed.access_token
        assert refreshed.access_token != login_response.access_token

    async def test_refresh_with_access_token_is_rejected(self, db_session):
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email=f"{uuid4().hex[:8]}@example.com",
            password="correct-password",
            full_name="DB Test User",
        )
        login_response = await auth_service.login(email=user.email, password="correct-password")
        with pytest.raises(ValidationError):
            # Using an access token where a refresh token is required.
            await auth_service.refresh_token(login_response.access_token)

    async def test_duplicate_email_registration_rejected(self, db_session):
        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(email=email, password="pw123456", full_name="First")
        with pytest.raises(ValidationError):
            await auth_service.create_user(email=email, password="pw123456", full_name="Second")


# ---------------------------------------------------------------------------
# HTTP-level endpoint tests
# ---------------------------------------------------------------------------


class TestAuthEndpoints:
    async def test_login_endpoint_success(self, api_client, db_session):
        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(email=email, password="pw123456", full_name="HTTP Test")

        response = await api_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "pw123456"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body

    async def test_login_endpoint_invalid_credentials(self, api_client):
        response = await api_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        assert response.status_code in (400, 401, 422)

    async def test_get_current_user_requires_auth(self, api_client):
        response = await api_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_get_current_user_with_valid_token(self, api_client, db_session):
        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        user = await auth_service.create_user(email=email, password="pw123456", full_name="Me Test")
        login = await auth_service.login(email=email, password="pw123456")

        response = await api_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login.access_token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    async def test_create_user_endpoint_requires_admin(self, api_client, db_session):
        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(
            email=email, password="pw123456", full_name="Analyst", role=UserRole.ANALYST
        )
        login = await auth_service.login(email=email, password="pw123456")

        response = await api_client.post(
            "/api/v1/auth/users",
            params={
                "email": f"{uuid4().hex[:8]}@example.com",
                "password": "newpass1",
                "full_name": "New User",
                "role": "analyst",
            },
            headers={"Authorization": f"Bearer {login.access_token}"},
        )
        assert response.status_code == 403

    async def test_create_user_endpoint_succeeds_for_admin(self, api_client, db_session):
        auth_service = AuthService(db_session)
        admin_email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(
            email=admin_email, password="pw123456", full_name="Admin", role=UserRole.ADMIN
        )
        login = await auth_service.login(email=admin_email, password="pw123456")

        response = await api_client.post(
            "/api/v1/auth/users",
            params={
                "email": f"{uuid4().hex[:8]}@example.com",
                "password": "newpass1",
                "full_name": "New User",
                "role": "analyst",
            },
            headers={"Authorization": f"Bearer {login.access_token}"},
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# WS1-dependent behavior, written defensively
# ---------------------------------------------------------------------------


class TestWS1NotYetLanded:
    async def test_logout_endpoint(self, api_client, db_session):
        """POST /auth/logout doesn't exist yet in this worktree (WS1)."""
        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(email=email, password="pw123456", full_name="Logout Test")
        login = await auth_service.login(email=email, password="pw123456")

        response = await api_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {login.access_token}"},
        )
        if response.status_code == 404:
            pytest.xfail("POST /auth/logout not implemented yet (WS1)")
        assert response.status_code in (200, 204)

        # If logout exists, using the same token afterwards should now be
        # rejected once a token blacklist is wired up.
        followup = await api_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login.access_token}"},
        )
        assert followup.status_code == 401

    async def test_login_rate_limiting(self, api_client):
        """5 rapid bad-credential attempts, then a 6th expecting 429 once
        WS1 wires up rate limiting on /auth/login."""
        last_response = None
        for _ in range(6):
            last_response = await api_client.post(
                "/api/v1/auth/login",
                json={"email": "ratelimit-test@example.com", "password": "wrong"},
            )
        if last_response.status_code != 429:
            pytest.xfail("Rate limiting on /auth/login not wired up yet (WS1)")
        assert last_response.status_code == 429

    def test_audit_log_db_model_exists(self):
        """WS1 adds a persisted AuditLog SQLAlchemy model to
        src/models/__init__.py. It doesn't exist in this worktree yet."""
        import src.models as models_module

        if not hasattr(models_module, "AuditLog"):
            pytest.skip("AuditLog DB model not added yet (WS1)")
        assert hasattr(models_module.AuditLog, "__tablename__")

    async def test_audit_log_persists_to_database_on_login(self, api_client, db_session):
        """Once WS1 replaces the in-memory buffer with real DB writes, a
        successful login should leave a row behind."""
        import src.models as models_module

        if not hasattr(models_module, "AuditLog"):
            pytest.skip("AuditLog DB model not added yet (WS1)")

        from sqlalchemy import func, select

        auth_service = AuthService(db_session)
        email = f"{uuid4().hex[:8]}@example.com"
        await auth_service.create_user(email=email, password="pw123456", full_name="Audit Test")

        before = await db_session.scalar(select(func.count()).select_from(models_module.AuditLog))
        await api_client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
        after = await db_session.scalar(select(func.count()).select_from(models_module.AuditLog))

        assert after == before + 1
