"""
Authentication API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    ACCESS_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    AuthService,
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
    clear_auth_cookies,
    get_current_user,
    limiter,
    require_admin,
    security,
    set_auth_cookies,
)
from src.core import get_logger, get_session, get_settings
from src.models import User
from src.schemas import PaginatedResponse

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["authentication"])


# NOTE (WS1): /login and /refresh are unauthenticated and were previously
# completely unthrottled -- a brute-force exposure. Strict per-IP limits
# via the shared `limiter` (defined in src.auth) close that gap.
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user credentials, set httpOnly access/refresh cookies, and return both tokens in the body for API clients.",
)
@limiter.limit(lambda: settings.AUTH_RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """User login - sets httpOnly access/refresh cookies and also returns
    both tokens in the body (for non-browser API clients)."""
    auth_service = AuthService(session)
    tokens = await auth_service.login(
        email=credentials.email,
        password=credentials.password,
        request=request,
    )
    set_auth_cookies(response, tokens)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh access token. Browsers rely on the refresh_token cookie; a non-browser client may pass refresh_token in the JSON body.",
)
@limiter.limit(lambda: settings.AUTH_RATE_LIMIT_REFRESH)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """Refresh access token. Browsers rely on the refresh_token cookie; a
    non-browser client may instead pass refresh_token in the JSON body."""
    token = body.refresh_token or request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )
    auth_service = AuthService(session)
    tokens = await auth_service.refresh_token(token)
    set_auth_cookies(response, tokens)
    return tokens


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
):
    """Log out the current session by revoking its access (and refresh) token
    and clearing the auth cookies."""
    access_token = (
        credentials.credentials if credentials else request.cookies.get(ACCESS_COOKIE_NAME)
    )
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(session)
    await auth_service.logout(
        access_token=access_token,
        refresh_token=request.cookies.get(REFRESH_COOKIE_NAME),
        request=request,
    )
    clear_auth_cookies(response)
    return {"status": "logged_out"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
    description="Retrieve the profile and permissions of the currently authenticated user.",
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.get(
    "/users",
    response_model=PaginatedResponse,
    summary="List users",
    description="List all users (admin only). Pagination and filtering supported.",
)
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


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user (admin only).",
)
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


@router.post(
    "/change-password",
    summary="Change password",
    description="Change the current user's password.",
)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Change current user's password."""
    auth_service = AuthService(session)
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
        request=request,
    )
    return {"status": "password_changed"}


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Activate/deactivate a user or change their role (admin only).",
)
async def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Activate/deactivate a user or change their role (admin only)."""
    from src.models import UserRole

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id and body.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account.",
        )

    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {body.role}. Valid roles: {[r.value for r in UserRole]}",
            ) from exc
    if body.is_active is not None:
        user.is_active = body.is_active

    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)
