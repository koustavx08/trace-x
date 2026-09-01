"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    AuthService,
    CreateUserRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    get_current_user,
    limiter,
    require_admin,
    security,
)
from src.core import get_logger, get_session
from src.models import User
from src.schemas import PaginatedResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


# NOTE (WS1): /login and /refresh are unauthenticated and were previously
# completely unthrottled -- a brute-force exposure. Strict per-IP limits
# via the shared `limiter` (defined in src.auth) close that gap.
@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """User login - returns access and refresh tokens."""
    auth_service = AuthService(session)
    return await auth_service.login(
        email=credentials.email,
        password=credentials.password,
        request=request,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
async def refresh_token(
    request: Request,
    refresh_token: str,
    session: AsyncSession = Depends(get_session),
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(session)
    return await auth_service.refresh_token(refresh_token)


@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    refresh_token: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Log out the current session by revoking its access (and refresh) token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(session)
    await auth_service.logout(
        access_token=credentials.credentials,
        refresh_token=refresh_token,
        request=request,
    )
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> PaginatedResponse:
    """List users (admin only)."""
    query = select(User).order_by(User.created_at.desc())

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0

    offset = (page - 1) * page_size
    result = await session.execute(query.offset(offset).limit(page_size))
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    body: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Create new user (admin only)."""
    from src.models import UserRole

    try:
        user_role = UserRole(body.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Valid roles: {[r.value for r in UserRole]}",
        ) from exc

    auth_service = AuthService(session)
    user = await auth_service.create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=user_role,
        request=request,
    )
    return UserResponse.model_validate(user)


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str,
    new_password: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Change current user's password."""
    auth_service = AuthService(session)
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=current_password,
        new_password=new_password,
        request=request,
    )
    return {"status": "password_changed"}
