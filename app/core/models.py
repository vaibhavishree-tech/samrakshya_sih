"""
Contains the database ORM schemas mapping directly to the architecture:

-RawDocument (Document Store): Stores un-truncated, raw JSON payloads using PostgreSQL JSONB alongside Unix timestamps.
-ThreatState (Shared Memory): Captures extracted entities, risk scores, and status flags, 
acting as the structured handoff point between agents.
-HistoricalIntelligence (Vector Store): Uses Vector(384) to store mathematical embeddings of known threat signatures directly in SQL rows.
-NetworkEdge (Knowledge Graph): Captures source_node, target_node, and interaction_type records to enable network topology mapping.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class RawDocument(Base):
    """Document Store: Raw, un-truncated JSON payloads from ingestion."""
    __tablename__ = "raw_osint_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_source = Column(String, index=True)
    raw_payload = Column(JSONB, nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow)

class ThreatState(Base):
    """Shared Memory: Central state store for agent handoffs and summaries."""
    __tablename__ = "threat_state"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("raw_osint_documents.id"), nullable=True)
    raw_text = Column(Text, nullable=False)
    extracted_entities = Column(JSONB, default=list)
    sentiment_profile = Column(JSONB, default=dict)
    risk_score = Column(Float, default=0.0)
    final_summary = Column(Text, nullable=True)  # Updated by teammate's Summarization Agent
    status = Column(String, default="PROCESSING")

class HistoricalIntelligence(Base):
    """Vector Store: Known threat signatures and embeddings for RAG verification."""
    __tablename__ = "historical_intelligence"
    
    id = Column(String, primary_key=True)
    title = Column(String)
    category = Column(String, index=True)
    content = Column(Text)
    embedding = Column(Vector(384))  # 384-dim vector column for pgvector

class NetworkEdge(Base):
    """Knowledge Graph: Relationship edges between user nodes for PageRank mapping."""
    __tablename__ = "network_edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    threat_state_id = Column(UUID(as_uuid=True), ForeignKey("threat_state.id"))
    source_node = Column(String, index=True)
    target_node = Column(String, index=True)
    interaction_type = Column(String) 
    interaction_timestamp = Column(DateTime, nullable=True)