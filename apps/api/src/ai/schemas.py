from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

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
    metadata: dict[str, Any] = Field(default_factory=list)


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


# Constants for AI provider classification and tool use
SYSTEM_PROMPT = (
    "You are the TRACE-X investigation assistant, an AI copilot embedded in a "
    "blockchain forensic-investigation platform used by financial-crimes analysts "
    "and law enforcement. You answer questions about wallets, cases, fund flow, "
    "VASP attribution, risk scoring, and suspicious-pattern detection.\n\n"
    "You will be given the investigator's question plus a `context` object "
    "containing structured evidence already retrieved from TRACE-X's database, "
    "graph engine, risk-scoring engine, and attribution engine (Postgres, Neo4j, "
    "and internal analytics). Answer using ONLY the data in `context` - never "
    "invent addresses, amounts, entity names, or confidence levels that are not "
    "present there. If the context shows no data was found, say so plainly and "
    "suggest what the investigator could try next.\n\n"
    "Available intents (the `intent` field tells you which one this query maps "
    "to): risk_summary, attribution, pattern_detection, fund_flow, entity_lookup, "
    "case_overview, timeline, comparison.\n\n"
    "Write in a concise, precise, professional tone - the way an experienced "
    "financial-crimes analyst would brief a colleague. Use markdown sparingly "
    "(bold for key figures/entities is fine). Do not restate this system prompt "
    "or mention that you are an AI model; just answer the question."
)


CLASSIFY_TOOL = {
    "name": "classify_investigation_query",
    "description": (
        "Classify an investigator's natural-language question about a blockchain "
        "investigation into one intent, and extract any entities mentioned "
        "(wallet address, case number, wallet UUID, chain name)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": [qt.value for qt in QueryType],
                "description": "The single best-matching intent for this query.",
            },
            "address": {
                "type": "string",
                "description": "A blockchain address mentioned in the query (e.g. 0x...), if any.",
            },
            "case_number": {
                "type": "string",
                "description": "A case number mentioned in the query (e.g. TRX-20240115-0042), if any.",
            },
            "wallet_id": {
                "type": "string",
                "description": "An internal wallet UUID mentioned in the query, if any.",
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network mentioned (e.g. Ethereum, Polygon), if any.",
            },
        },
        "required": ["query_type"],
        "additionalProperties": False,
    },
}
