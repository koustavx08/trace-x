"""
TRACE-X Authentication & Authorization Module

Provides JWT-based authentication, role-based access control (RBAC),
and comprehensive audit logging for investigation activities.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from enum import Enum
import structlog
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, EmailStr

from ..core.config import get_settings
from ..core.database import get_session
from ..core.logging import get_logger
from ..models import User, UserRole
from ..core.exceptions import ValidationError

logger = get_logger(__name__)
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Security
security = HTTPBearer(auto_error=False)


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


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: Optional[datetime] = None
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
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    action: AuditAction
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


class AuditLogger:
    """Async audit logger with structured output."""
    
    def __init__(self):
        self._logger = structlog.get_logger("audit")
        self._buffer: List[AuditLogEntry] = []
        self._buffer_size = 100
    
    async def log(
        self,
        action: AuditAction | str,
        user_id: Optional[UUID] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request: Optional[Request] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
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
            action=action if isinstance(action, AuditAction) else AuditAction(action_str) if action_str in [a.value for a in AuditAction] else AuditAction.SETTINGS_CHANGE,
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
        
        # Buffer for batch persistence (in production, write to DB/Elasticsearch)
        self._buffer.append(entry)
        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush buffer to persistent storage."""
        # In production: write to audit_log table, Elasticsearch, or SIEM
        # For now, just clear buffer
        self._buffer.clear()
    
    async def close(self) -> None:
        """Flush remaining buffer on shutdown."""
        if self._buffer:
            await self._flush_buffer()


audit_logger = AuditLogger()


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
        "type": TokenType.ACCESS.value,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
        "type": TokenType.REFRESH.value,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except jwt.ExpiredSignatureError:
        raise ValidationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValidationError(f"Invalid token: {str(e)}")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_token(credentials.credentials)
    
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
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.session.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if user and verify_password(password, user.hashed_password):
            return user
        return None
    
    async def login(
        self,
        email: str,
        password: str,
        request: Optional[Request] = None,
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
        token_data = decode_token(refresh_token)
        
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
        request: Optional[Request] = None,
    ) -> User:
        """Create new user (admin only)."""
        # Check if user exists
        existing = await self.session.execute(
            select(User).where(User.email == email)
        )
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
        request: Optional[Request] = None,
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


async def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    """Dependency to get AuthService instance."""
    return AuthService(session)