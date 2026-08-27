"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from ....core import get_session, get_logger
from ....auth import (
    AuthService,
    LoginRequest,
    TokenResponse,
    UserResponse,
    get_current_user,
    require_admin,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
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
async def refresh_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_session),
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(session)
    return await auth_service.refresh_token(refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    email: EmailStr,
    password: str,
    full_name: str,
    role: str = "analyst",
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Create new user (admin only)."""
    from ....models import UserRole
    try:
        user_role = UserRole(role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Valid roles: {[r.value for r in UserRole]}",
        )
    
    auth_service = AuthService(session)
    user = await auth_service.create_user(
        email=email,
        password=password,
        full_name=full_name,
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