from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    Integer,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..core.database import Base
import enum


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CrimeType(str, enum.Enum):
    FRAUD = "fraud"
    MONEY_LAUNDERING = "money_laundering"
    RANSOMWARE = "ransomware"
    DARKNET_MARKET = "darknet_market"
    SANCTIONS_EVASION = "sanctions_evasion"
    OTHER = "other"


class UserRole(str, enum.Enum):
    ANALYST = "analyst"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class AttributionStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    UNDER_REVIEW = "under_review"
    ATTRIBUTED = "attributed"
    CONFIRMED = "confirmed"


class InvestigationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.ANALYST, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assigned_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="assignee", foreign_keys="Case.assigned_to"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    crime_type: Mapped[CrimeType] = mapped_column(
        SQLEnum(CrimeType), default=CrimeType.FRAUD, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False
    )
    assigned_to: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assignee: Mapped[User | None] = relationship(
        "User", back_populates="assigned_cases", foreign_keys=[assigned_to]
    )
    wallets: Mapped[list["Wallet"]] = relationship(
        "Wallet", back_populates="case", cascade="all, delete-orphan"
    )
    investigation_runs: Mapped[list["InvestigationRun"]] = relationship(
        "InvestigationRun", back_populates="case", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="case", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cases_status_created", "status", "created_at"),
        Index("ix_cases_assignee_status", "assigned_to", "status"),
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, case_number={self.case_number}, title={self.title})>"


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    chain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_status: Mapped[AttributionStatus] = mapped_column(
        SQLEnum(AttributionStatus), default=AttributionStatus.UNVERIFIED, nullable=False
    )
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_seen_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    case: Mapped[Case] = relationship("Case", back_populates="wallets")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="wallet", cascade="all, delete-orphan"
    )
    investigation_runs: Mapped[list["InvestigationRun"]] = relationship(
        "InvestigationRun", back_populates="wallet", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wallets_case_chain", "case_id", "chain"),
        Index("ix_wallets_address_chain", "address", "chain", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, address={self.address}, chain={self.chain})>"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    wallet_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tx_hash: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    block_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    from_address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    to_address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(78), nullable=False)
    value_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    token_address: Mapped[str | None] = mapped_column(String(66), nullable=True)
    token_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(default=False, nullable=False)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    wallet: Mapped[Wallet] = relationship("Wallet", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_wallet_timestamp", "wallet_id", "timestamp"),
        Index("ix_transactions_tx_hash", "tx_hash", unique=True),
        Index("ix_transactions_from_to", "from_address", "to_address"),
    )

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, tx_hash={self.tx_hash[:10]}...)>"


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wallet_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        SQLEnum(InvestigationStatus), default=InvestigationStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    case: Mapped[Case] = relationship("Case", back_populates="investigation_runs")
    wallet: Mapped[Wallet] = relationship("Wallet", back_populates="investigation_runs")

    __table_args__ = (
        Index("ix_investigation_runs_case_status", "case_id", "status"),
        Index("ix_investigation_runs_wallet_status", "wallet_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<InvestigationRun(id={self.id}, case_id={self.case_id}, status={self.status})>"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_run_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("investigation_runs.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_assessment: Mapped[dict] = mapped_column(JSON, nullable=False)
    graph_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_by: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(10), default="json", nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    case: Mapped[Case] = relationship("Case", back_populates="reports")
    investigation_run: Mapped["InvestigationRun | None"] = relationship()

    __table_args__ = (
        Index("ix_reports_case_created", "case_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, case_id={self.case_id}, title={self.title})>"