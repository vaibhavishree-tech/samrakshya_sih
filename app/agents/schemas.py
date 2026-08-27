"""
Strict Pydantic guardrails for the agents
This file defines the exact JSON structure every agent must return.
The LLMs will physically not be able to output responses that violate these contracts.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class Entity(BaseModel):
    name: str = Field(..., description="The exact extracted entity (e.g., @node_alpha, #MidnightWalk)")
    entity_type: Literal["PERSON", "ORGANIZATION", "LOCATION", "HASHTAG", "HANDLE"] = Field(
        ..., description="The category of the extracted entity"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence score from 0.0 to 1.0"
    )
    is_suspicious: bool = Field(
        ..., description="True if entity shows flags like secrecy, fake accounts, or predatory keywords"
    )
    suspicion_reason: Optional[str] = Field(
        None, description="Reason for flagging entity as suspicious; null if false"
    )


class ExtractedEntities(BaseModel):
    entities: List[Entity] = Field(default_factory=list)


class VerificationResult(BaseModel):
    is_known_threat: bool = Field(
        ..., description="True if any suspicious entity matches historical DB threat intelligence"
    )
    matched_category: Optional[str] = Field(
        None, description="The matched threat category from the DB if verified"
    )
    reasoning: str = Field(..., description="Detailed explanation of the RAG verification finding")


class Edge(BaseModel):
    source_node: str = Field(..., description="The originating handle or account initiating the interaction")
    target_node: str = Field(..., description="The target handle, account, or hashtag receiving the interaction")
    interaction_type: Literal["MENTION", "REPLY", "SHARE"] = Field(
        ..., description="The type of interaction between source and target"
    )
    timestamp: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp of the interaction if present in the source data. "
        "Null if the raw payload carries no timing information.",
    )


class NetworkEdges(BaseModel):
    edges: List[Edge] = Field(default_factory=list)


class AlertAnalysis(BaseModel):
    velocity_detected: bool = Field(
        ...,
        description="True only if edge timestamps show an anomalous spike (many edges in a short window) "
        "or edge density/fan-out indicates botnet-like propagation. Must be grounded in `edges` "
        "timing/count data actually provided, never inferred from tone or wording alone.",
    )
    risk_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final combined anomaly risk score from 0.0 to 100.0"
    )
    reasoning: str = Field(
        ..., description="Qualitative justification for the final score, breaking down key factors"
    )