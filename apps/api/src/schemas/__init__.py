from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class CaseStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CrimeType(str, Enum):
    FRAUD = "fraud"
    MONEY_LAUNDERING = "money_laundering"
    RANSOMWARE = "ransomware"
    DARKNET_MARKET = "darknet_market"
    SANCTIONS_EVASION = "sanctions_evasion"
    OTHER = "other"


class UserRole(str, Enum):
    ANALYST = "analyst"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class AttributionStatus(str, Enum):
    UNVERIFIED = "unverified"
    UNDER_REVIEW = "under_review"
    ATTRIBUTED = "attributed"
    CONFIRMED = "confirmed"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    CONFIRMED = "CONFIRMED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    PROBABLE = "PROBABLE"
    UNKNOWN = "UNKNOWN"


class UserBase(BaseModel):
    email: str = Field(..., max_length=255)
    full_name: str = Field(..., max_length=255)
    role: UserRole = UserRole.ANALYST


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CaseBase(BaseModel):
    title: str = Field(..., max_length=255)
    crime_type: CrimeType = CrimeType.FRAUD
    description: str
    status: CaseStatus = CaseStatus.OPEN


class CaseCreate(CaseBase):
    assigned_to: Optional[UUID] = None
    metadata: Optional[dict] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    crime_type: Optional[CrimeType] = None
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    assigned_to: Optional[UUID] = None
    metadata: Optional[dict] = None


class CaseResponse(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    assigned_to: Optional[UUID] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class WalletBase(BaseModel):
    address: str = Field(..., max_length=66)
    chain: str = Field(..., max_length=50)
    label: Optional[str] = Field(None, max_length=100)
    attribution_status: AttributionStatus = AttributionStatus.UNVERIFIED
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    entity_name: Optional[str] = Field(None, max_length=255)
    entity_confidence: Optional[ConfidenceLevel] = None
    first_seen_tx_hash: Optional[str] = Field(None, max_length=66)
    metadata: Optional[dict] = None


class WalletCreate(WalletBase):
    pass


class WalletUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    attribution_status: Optional[AttributionStatus] = None
    risk_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    entity_name: Optional[str] = Field(None, max_length=255)
    entity_confidence: Optional[ConfidenceLevel] = None
    first_seen_tx_hash: Optional[str] = Field(None, max_length=66)
    metadata: Optional[dict] = None


class WalletResponse(WalletBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    created_at: datetime
    updated_at: datetime


class TransactionBase(BaseModel):
    tx_hash: str = Field(..., max_length=66)
    block_number: int
    timestamp: datetime
    from_address: str = Field(..., max_length=66)
    to_address: str = Field(..., max_length=66)
    value: str
    value_usd: Optional[float] = None
    token_address: Optional[str] = Field(None, max_length=66)
    token_symbol: Optional[str] = Field(None, max_length=20)
    method: Optional[str] = Field(None, max_length=100)
    is_suspicious: bool = False
    metadata: Optional[dict] = None


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    created_at: datetime


class InvestigationRunBase(BaseModel):
    config: Optional[dict] = None


class InvestigationRunCreate(InvestigationRunBase):
    pass


class InvestigationRunUpdate(BaseModel):
    status: Optional[InvestigationStatus] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None


class InvestigationRunResponse(InvestigationRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    wallet_id: UUID
    status: InvestigationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ReportBase(BaseModel):
    title: str = Field(..., max_length=255)
    summary: str
    findings: dict
    risk_assessment: dict
    graph_snapshot: Optional[dict] = None
    format: str = Field(default="json", pattern="^(pdf|json|html)$")


class ReportCreate(ReportBase):
    investigation_run_id: Optional[UUID] = None


class ReportResponse(ReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    investigation_run_id: Optional[UUID] = None
    generated_by: UUID
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: dict