from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    email: str | None = Field(None, max_length=255)
    full_name: str | None = Field(None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CaseBase(BaseModel):
    title: str = Field(..., max_length=255)
    crime_type: CrimeType = CrimeType.FRAUD
    description: str
    status: CaseStatus = CaseStatus.OPEN


class CaseCreate(CaseBase):
    assigned_to: UUID | None = None
    metadata: dict | None = None


class CaseUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    crime_type: CrimeType | None = None
    description: str | None = None
    status: CaseStatus | None = None
    assigned_to: UUID | None = None
    metadata: dict | None = None


class CaseResponse(CaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    assigned_to: UUID | None = None
    # The ORM attribute is `case_metadata` -- `metadata` is reserved by
    # SQLAlchemy's Declarative API. Validating this response straight off a
    # `Case` object without the alias picked up SQLAlchemy's own
    # `Case.metadata` (a `MetaData` instance) and raised a ValidationError,
    # turning every list/detail case request into a 500. The public JSON field
    # stays `metadata`; only the attribute it is read from changes.
    metadata: dict | None = Field(
        default=None, validation_alias=AliasChoices("case_metadata", "metadata")
    )
    created_at: datetime
    updated_at: datetime


class WalletBase(BaseModel):
    address: str = Field(..., max_length=66)
    chain: str = Field(..., max_length=50)
    label: str | None = Field(None, max_length=100)
    attribution_status: AttributionStatus = AttributionStatus.UNVERIFIED
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    entity_name: str | None = Field(None, max_length=255)
    entity_confidence: ConfidenceLevel | None = None
    first_seen_tx_hash: str | None = Field(None, max_length=66)
    metadata: dict | None = None


class WalletCreate(WalletBase):
    pass


class WalletUpdate(BaseModel):
    label: str | None = Field(None, max_length=100)
    attribution_status: AttributionStatus | None = None
    risk_score: float | None = Field(None, ge=0.0, le=100.0)
    entity_name: str | None = Field(None, max_length=255)
    entity_confidence: ConfidenceLevel | None = None
    first_seen_tx_hash: str | None = Field(None, max_length=66)
    metadata: dict | None = None


class WalletResponse(WalletBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    # See CaseResponse.metadata -- the ORM attribute is `wallet_metadata`.
    metadata: dict | None = Field(
        default=None, validation_alias=AliasChoices("wallet_metadata", "metadata")
    )
    created_at: datetime
    updated_at: datetime


class TransactionBase(BaseModel):
    tx_hash: str = Field(..., max_length=66)
    block_number: int
    timestamp: datetime
    from_address: str = Field(..., max_length=66)
    to_address: str = Field(..., max_length=66)
    value: str
    value_usd: float | None = None
    token_address: str | None = Field(None, max_length=66)
    token_symbol: str | None = Field(None, max_length=20)
    method: str | None = Field(None, max_length=100)
    is_suspicious: bool = False
    metadata: dict | None = None


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    # See CaseResponse.metadata -- the ORM attribute is `transaction_metadata`.
    metadata: dict | None = Field(
        default=None, validation_alias=AliasChoices("transaction_metadata", "metadata")
    )
    created_at: datetime


class InvestigationRunBase(BaseModel):
    config: dict | None = None


class InvestigationRunCreate(InvestigationRunBase):
    pass


class InvestigationRunUpdate(BaseModel):
    status: InvestigationStatus | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict | None = None


class InvestigationRunResponse(InvestigationRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    wallet_id: UUID
    status: InvestigationStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict | None = None
    created_at: datetime
    updated_at: datetime


class ReportBase(BaseModel):
    title: str = Field(..., max_length=255)
    summary: str
    findings: dict
    risk_assessment: dict
    graph_snapshot: dict | None = None
    format: str = Field(default="json", pattern="^(pdf|json|html)$")


class ReportCreate(ReportBase):
    investigation_run_id: UUID | None = None


class ReportResponse(ReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    investigation_run_id: UUID | None = None
    generated_by: UUID
    file_path: str | None = None
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
