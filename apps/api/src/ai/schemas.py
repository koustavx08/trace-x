from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryType(str, Enum):
    RISK_SUMMARY = "risk_summary"
    ATTRIBUTION = "attribution"
    PATTERN_DETECTION = "pattern_detection"
    FUND_FLOW = "fund_flow"
    ENTITY_LOOKUP = "entity_lookup"
    CASE_OVERVIEW = "case_overview"
    TIMELINE = "timeline"
    COMPARISON = "comparison"


class ConfidenceLevel(str, Enum):
    CONFIRMED = "CONFIRMED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    PROBABLE = "PROBABLE"
    UNKNOWN = "UNKNOWN"


class Evidence(BaseModel):
    # from_attributes: service.Evidence (the AI assistant's internal result
    # type) is a plain dataclass, not this pydantic model -- without this,
    # constructing AIQueryResponse(evidence=response.evidence, ...) raises a
    # ValidationError on every query that returns evidence (i.e. almost all
    # of them), since pydantic won't build a model from an arbitrary object's
    # attributes unless told to.
    model_config = ConfigDict(from_attributes=True)

    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AIQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    case_id: str | None = None
    wallet_id: str | None = None


class AIQueryResponse(BaseModel):
    answer: str
    query_type: QueryType
    confidence: ConfidenceLevel
    evidence: list[Evidence]
    follow_up_questions: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    session_id: str
    case_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    case_id: str | None = None
    wallet_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage
    suggested_actions: list[str] = Field(default_factory=list)
