"""
TRACE-X Authentication & Authorization Module

Provides JWT-based authentication, role-based access control (RBAC),
and comprehensive audit logging for investigation activities.
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

import bcrypt
import jwt
import redis.asyncio as redis
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.database import async_session_factory, get_session
from src.core.exceptions import ValidationError
from src.core.logging import get_logger
from src.models import AuditLog, User, UserRole

logger = get_logger(__name__)
settings = get_settings()

# --- WS1 auth hardening: shared rate limiter ---
# Defined here (not in main.py) so both main.py (middleware registration)
# and api/v1/auth.py (per-route @limiter.limit(...) decorators) can import
# the same Limiter instance.
limiter = Limiter(key_func=get_remote_address)
# --- end shared rate limiter ---

# Password hashing (bcrypt used directly -- passlib 1.7.4's bcrypt backend is
# incompatible with bcrypt>=4.1, which enforces the 72-byte secret limit that
# passlib's internal calibration routine violates, breaking every hash/verify
# call: https://github.com/pyca/bcrypt/issues/684)

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Security
security = HTTPBearer(auto_error=False)

# --- WS1 auth hardening: Redis-backed JTI blacklist (for /auth/logout) ---
_redis_client: Optional["redis.Redis"] = None
_BLACKLIST_KEY_PREFIX = "auth:blacklist:jti:"


def _get_redis_client() -> "redis.Redis":
    """Lazily create a shared Redis client, reusing the configured REDIS_URL."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def blacklist_token(jti: str, expires_at: datetime) -> None:
    """Add a token's JTI to the revocation blacklist until it would have expired."""
    # PyJWT/pydantic decode `exp` into a tz-aware (UTC) datetime, whereas the
    # rest of this module mints tokens using naive datetime.utcnow(). Coerce
    # both sides to aware UTC before subtracting so this works either way.
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    ttl_seconds = int((expires_at - now).total_seconds())
    if ttl_seconds <= 0:
        # Already expired -- no need to blacklist, decode will reject it anyway.
        return
    client = _get_redis_client()
    try:
        await client.setex(f"{_BLACKLIST_KEY_PREFIX}{jti}", ttl_seconds, "1")
    except Exception as exc:  # pragma: no cover - Redis unavailable
        logger.error("token_blacklist_write_failed", jti=jti, error=str(exc))
        raise


async def is_token_blacklisted(jti: str) -> bool:
    """Check whether a token's JTI has been revoked."""
    client = _get_redis_client()
    try:
        return bool(await client.exists(f"{_BLACKLIST_KEY_PREFIX}{jti}"))
    except Exception as exc:  # pragma: no cover - Redis unavailable
        # Fail closed on auth security checks only when we can positively
        # confirm revocation; if Redis itself is down, log and allow the
        # request through rather than taking the whole API offline.
        logger.error("token_blacklist_read_failed", jti=jti, error=str(exc))
        return False


# --- end Redis-backed JTI blacklist ---


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenData(BaseModel):
    sub: str  # user_id
    email: str
    role: UserRole
    type: TokenType
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "analyst"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = None


class UserResponse(BaseModel):
    # WS1 fix: without this, UserResponse.model_validate(<User ORM object>)
    # (used by GET /auth/me) raises a pydantic ValidationError on every call,
    # which blocked verifying the logout/blacklist flow end-to-end.
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    CASE_CREATE = "case_create"
    CASE_READ = "case_read"
    CASE_UPDATE = "case_update"
    CASE_DELETE = "case_delete"
    WALLET_CREATE = "wallet_create"
    WALLET_READ = "wallet_read"
    WALLET_UPDATE = "wallet_update"
    WALLET_DELETE = "wallet_delete"
    WALLET_ANALYZE = "wallet_analyze"
    INVESTIGATION_START = "investigation_start"
    INVESTIGATION_READ = "investigation_read"
    REPORT_GENERATE = "report_generate"
    REPORT_DOWNLOAD = "report_download"
    GRAPH_QUERY = "graph_query"
    AI_QUERY = "ai_query"
    ENTITY_LOOKUP = "entity_lookup"
    SETTINGS_CHANGE = "settings_change"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    EXPORT_DATA = "export_data"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


class AuditLogEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: UUID | None = None
    user_email: str | None = None
    action: AuditAction
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class AuditLogger:
    """Async audit logger with structured output."""

    def __init__(self):
        self._logger = structlog.get_logger("audit")
        # Retained only as a resilience fallback: entries that fail to
        # persist immediately (e.g. transient DB outage) land here and are
        # retried by _flush_buffer(), including on shutdown via close().
        self._buffer: list[AuditLogEntry] = []

    async def log(
        self,
        action: AuditAction | str,
        user_id: UUID | None = None,
        user_email: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request: Request | None = None,
        success: bool = True,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        """Log an audit event."""
        ip = None
        ua = None
        if request:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")

        action_str = action.value if isinstance(action, AuditAction) else action

        entry = AuditLogEntry(
            user_id=user_id,
            user_email=user_email,
            action=action
            if isinstance(action, AuditAction)
            else AuditAction(action_str)
            if action_str in [a.value for a in AuditAction]
            else AuditAction.SETTINGS_CHANGE,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip,
            user_agent=ua,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
            session_id=session_id,
        )

        # Log to structured logger
        self._logger.info(
            "audit_event",
            audit_id=str(entry.id),
            timestamp=entry.timestamp.isoformat(),
            user_id=str(entry.user_id) if entry.user_id else None,
            user_email=entry.user_email,
            action=action_str,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            ip_address=entry.ip_address,
            success=entry.success,
            error_message=entry.error_message,
            metadata=entry.metadata,
        )

        # Persist immediately to the audit_log table.
        await self._persist(entry)

    async def _persist(self, entry: AuditLogEntry) -> None:
        """Write a single audit entry to the audit_log table.

        On failure the entry is retained in the in-memory buffer so it can
        be retried (via _flush_buffer / close) rather than silently lost.
        """
        action_value = (
            entry.action.value if isinstance(entry.action, AuditAction) else str(entry.action)
        )
        try:
            async with async_session_factory() as session:
                session.add(
                    AuditLog(
                        id=entry.id,
                        actor_id=entry.user_id,
                        action=action_value,
                        resource_type=entry.resource_type,
                        resource_id=entry.resource_id,
                        audit_metadata={
                            **entry.metadata,
                            "user_email": entry.user_email,
                            "user_agent": entry.user_agent,
                            "success": entry.success,
                            "error_message": entry.error_message,
                            "session_id": entry.session_id,
                        },
                        created_at=entry.timestamp,
                        ip_address=entry.ip_address,
                    )
                )
                await session.commit()
        except Exception as exc:
            self._logger.error(
                "audit_persist_failed",
                audit_id=str(entry.id),
                action=action_value,
                error=str(exc),
            )
            self._buffer.append(entry)

    async def _flush_buffer(self) -> None:
        """Retry persisting any buffered entries that failed to write immediately."""
        if not self._buffer:
            return
        pending, self._buffer = self._buffer, []
        for entry in pending:
            await self._persist(entry)

    async def close(self) -> None:
        """Flush remaining buffer on shutdown."""
        if self._buffer:
            await self._flush_buffer()


audit_logger = AuditLogger()


def hash_password(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid4()),
            "type": TokenType.ACCESS.value,
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": str(uuid4()),
            "type": TokenType.REFRESH.value,
        }
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def _decode_token_payload(token: str) -> TokenData:
    """Decode and signature/expiry-validate a JWT, without checking the blacklist."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except jwt.ExpiredSignatureError as e:
        raise ValidationError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise ValidationError(f"Invalid token: {str(e)}") from e


async def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token, rejecting revoked (blacklisted) tokens."""
    token_data = _decode_token_payload(token)
    if await is_token_blacklisted(token_data.jti):
        raise ValidationError("Token has been revoked")
    return token_data


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # WS1 fix: decode_token() raises the *custom* ValidationError (422) for
    # expired/malformed/revoked tokens. An auth dependency should surface
    # all of those uniformly as 401, not 422 -- most importantly so a
    # blacklisted (logged-out) token comes back as 401, as required.
    try:
        token_data = await decode_token(credentials.credentials)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc.message) if hasattr(exc, "message") else str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if token_data.type != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = await session.get(User, UUID(token_data.sub))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (alias for clarity)."""
    return current_user


def require_role(*allowed_roles: UserRole):
    """Dependency to require specific role(s)."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            await audit_logger.log(
                action=AuditAction.CASE_READ,  # Generic action for auth failure
                user_id=current_user.id,
                user_email=current_user.email,
                success=False,
                error_message=f"Insufficient permissions. Required: {[r.value for r in allowed_roles]}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Role-specific dependencies
require_admin = require_role(UserRole.ADMIN)
require_supervisor = require_role(UserRole.SUPERVISOR, UserRole.ADMIN)
require_analyst = require_role(UserRole.ANALYST, UserRole.SUPERVISOR, UserRole.ADMIN)


class AuthService:
    """Authentication service for login, registration, token management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def authenticate(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password."""
        result = await self.session.execute(select(User).where(User.email == email, User.is_active))
        user = result.scalar_one_or_none()

        if user and verify_password(password, user.hashed_password):
            return user
        return None

    async def login(
        self,
        email: str,
        password: str,
        request: Request | None = None,
    ) -> TokenResponse:
        """User login - returns access and refresh tokens."""
        user = await self.authenticate(email, password)

        if not user:
            await audit_logger.log(
                action=AuditAction.LOGIN_FAILED,
                user_email=email,
                request=request,
                success=False,
                error_message="Invalid credentials",
            )
            raise ValidationError("Invalid email or password")

        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.session.commit()

        # Create tokens
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        await audit_logger.log(
            action=AuditAction.LOGIN,
            user_id=user.id,
            user_email=user.email,
            request=request,
            success=True,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        token_data = await decode_token(refresh_token)

        if token_data.type != TokenType.REFRESH:
            raise ValidationError("Invalid token type")

        user = await self.session.get(User, UUID(token_data.sub))
        if not user or not user.is_active:
            raise ValidationError("User not found or inactive")

        new_token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
        access_token = create_access_token(new_token_data)
        new_refresh_token = create_refresh_token(new_token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.ANALYST,
        request: Request | None = None,
    ) -> User:
        """Create new user (admin only)."""
        # Check if user exists
        existing = await self.session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValidationError("User with this email already exists")

        user = User(
            id=uuid4(),
            email=email,
            full_name=full_name,
            role=role,
            hashed_password=hash_password(password),
            is_active=True,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        await audit_logger.log(
            action=AuditAction.USER_CREATE,
            user_id=user.id,
            user_email=user.email,
            request=request,
            success=True,
            metadata={"created_role": role.value},
        )

        return user

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        request: Request | None = None,
    ) -> bool:
        """Change user password."""
        user = await self.session.get(User, user_id)
        if not user:
            raise ValidationError("User not found")

        if not verify_password(current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        await self.session.commit()

        await audit_logger.log(
            action=AuditAction.USER_UPDATE,
            user_id=user.id,
            user_email=user.email,
            request=request,
            success=True,
            metadata={"action": "password_change"},
        )

        return True

    # --- WS1 auth hardening: real /auth/logout support ---
    async def logout(
        self,
        access_token: str,
        refresh_token: str | None = None,
        request: Request | None = None,
    ) -> None:
        """Revoke the caller's access token (and refresh token, if provided).

        Blacklists each token's JTI in Redis with a TTL equal to its
        remaining lifetime, so subsequent use of either token is rejected
        by decode_token()/get_current_user() until it would have expired
        naturally anyway.
        """
        access_data = _decode_token_payload(access_token)
        await blacklist_token(access_data.jti, access_data.exp)

        if refresh_token:
            try:
                refresh_data = _decode_token_payload(refresh_token)
                await blacklist_token(refresh_data.jti, refresh_data.exp)
            except ValidationError:
                # Refresh token already invalid/expired -- nothing to revoke.
                pass

        await audit_logger.log(
            action=AuditAction.LOGOUT,
            user_id=UUID(access_data.sub),
            user_email=access_data.email,
            request=request,
            success=True,
        )

    # --- end /auth/logout support ---


async def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    """Dependency to get AuthService instance."""
    return AuthService(session)
