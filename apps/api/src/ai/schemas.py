from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


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
    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AIQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    case_id: Optional[str] = None
    wallet_id: Optional[str] = None


class AIQueryResponse(BaseModel):
    answer: str
    query_type: QueryType
    confidence: ConfidenceLevel
    evidence: List[Evidence]
    follow_up_questions: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    session_id: str
    case_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    case_id: Optional[str] = None
    wallet_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage
    suggested_actions: List[str] = Field(default_factory=list)