import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def _pg_enum(enum_cls: type[enum.Enum]) -> SQLEnum:
    """Build a PG ENUM column type whose labels are the enum *values*.

    SQLAlchemy's default is to persist the member *name* ("OPEN"), but
    alembic/versions/001_initial.py declares every one of these types with the
    lowercase member values ('open', 'in_progress', ...). Without
    `values_callable` the two disagree, and any INSERT against a
    migration-provisioned database fails with `invalid input value for enum
    casestatus: "OPEN"`. Tests never caught this because they build the schema
    with `Base.metadata.create_all` instead of running the migrations.
    """
    return SQLEnum(enum_cls, values_callable=lambda e: [member.value for member in e])


class UserRole(str, enum.Enum):
    ANALYST = "analyst"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


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

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        _pg_enum(UserRole), default=UserRole.ANALYST, nullable=False
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

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    crime_type: Mapped[CrimeType] = mapped_column(
        _pg_enum(CrimeType), default=CrimeType.FRAUD, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        _pg_enum(CaseStatus), default=CaseStatus.OPEN, nullable=False
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    case_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    chain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_status: Mapped[AttributionStatus] = mapped_column(
        _pg_enum(AttributionStatus), default=AttributionStatus.UNVERIFIED, nullable=False
    )
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_seen_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    wallet_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
        # Uniqueness is per *case*, not global. Wallets belong to a case
        # (case_id is a non-null FK), and unrelated investigations routinely
        # touch the same address -- exchange deposit wallets, mixers, bridges
        # and token contracts recur across cases by their very nature. A global
        # unique (address, chain) made the second case to reference any such
        # address fail on insert. src/services/wallet_analysis.py already
        # encodes the intended rule, rejecting duplicates with "Wallet already
        # tracked in this case" scoped to (case_id, address, chain); this index
        # now matches that guard instead of contradicting it.
        Index("ix_wallets_address_chain", "case_id", "address", "chain", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, address={self.address}, chain={self.chain})>"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    wallet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # No `index=True` here: it would auto-generate an index also named
    # "ix_transactions_tx_hash", colliding with the explicit UNIQUE index of
    # that name in __table_args__ below. Two same-named indexes in the metadata
    # made `Base.metadata.create_all` fail with DuplicateTableError on any
    # fresh database -- which is why every database-backed test skipped.
    tx_hash: Mapped[str] = mapped_column(String(66), nullable=False)
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
    transaction_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
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

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        _pg_enum(InvestigationStatus), default=InvestigationStatus.PENDING, nullable=False
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

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("investigation_runs.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_assessment: Mapped[dict] = mapped_column(JSON, nullable=False)
    graph_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_by: Mapped[UUID] = mapped_column(
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

    __table_args__ = (Index("ix_reports_case_created", "case_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, case_id={self.case_id}, title={self.title})>"


# --- WS1 auth hardening: AuditLog model (append-only addition) ---
class AuditLog(Base):
    """Persistent audit trail entry.

    Backs `src.auth.AuditLogger`, which previously buffered entries
    in-memory only and dropped them on flush.
    """

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Attribute renamed to avoid colliding with SQLAlchemy's reserved
    # `Base.metadata`, matching the existing convention used by
    # `case_metadata` / `wallet_metadata` / `transaction_metadata` above.
    # The underlying DB column is still named "metadata".
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (Index("ix_audit_log_actor_created", "actor_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, actor_id={self.actor_id})>"


# --- end AuditLog model ---
