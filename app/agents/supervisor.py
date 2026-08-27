"""
Supervisor Orchestration Engine.
Coordinates the multi-agent pipeline sequentially, computes deterministic scoring baselines,
and persists state and network edges into PostgreSQL.
"""
from app.agents.core_agents import summarization_agent
from sqlalchemy import select
import re
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models import ThreatState, NetworkEdge
from app.agents.core_agents import (
    extraction_agent, verification_agent, link_analysis_agent, alerting_agent
)
from app.agents.schemas import (
    ExtractedEntities, VerificationResult, NetworkEdges, AlertAnalysis
)

def parse_agent_output(response, schema_class):
    """
    Bulletproof parser that uses RegEx to extract JSON from chatty LLM responses,
    and provides safe fallbacks to prevent pipeline crashes.
    """
    # Safely get content, defaulting to empty string if None
    content = getattr(response, "content", "")
    if content is None:
        content = ""
    
    # 1. If Agno parsed it natively
    if isinstance(content, schema_class):
        return content.model_dump()
    if isinstance(content, dict):
        return schema_class(**content).model_dump()
        
    # 2. If it is a raw string
    if isinstance(content, str):
        if not content.strip():
            print(f"⚠️ Warning: Agent returned empty string for {schema_class.__name__}")
            return _get_safe_fallback(schema_class)
            
        # Use RegEx to aggressively find the first JSON object block, ignoring text before/after
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        clean_content = json_match.group(0) if json_match else content.strip()
        
        try:
            data_dict = json.loads(clean_content)
            return schema_class(**data_dict).model_dump()
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️ Failed to parse JSON for {schema_class.__name__}. Raw: {content}")
            return _get_safe_fallback(schema_class)
            
    raise TypeError(f"Unsupported agent response content type: {type(content)}")

def _get_safe_fallback(schema_class):
    """Provides a safe empty dictionary matching the schema structure if the LLM fails completely."""
    if schema_class.__name__ == "ExtractedEntities":
        return {"entities": []}
    elif schema_class.__name__ == "VerificationResult":
        return {"is_known_threat": False, "matched_category": None, "reasoning": "LLM output unparseable."}
    elif schema_class.__name__ == "NetworkEdges":
        return {"edges": []}
    elif schema_class.__name__ == "AlertAnalysis":
        return {"velocity_detected": False, "risk_score": 50.0, "reasoning": "LLM output unparseable."}
    return {}

async def process_threat_pipeline(raw_text: str, session: AsyncSession, document_id: str = None) -> dict:
    """
    Executes the full 4-agent security pipeline sequentially.
    """

    # ---------------------------------------------------------
    # STEP 1: Extraction & Triage
    # ---------------------------------------------------------
    ext_response = await extraction_agent.arun(raw_text)
    extracted_data = parse_agent_output(ext_response, ExtractedEntities)
    entities = extracted_data.get("entities", [])

    # Optimization/Guardrail: Empty-path short-circuiting for benign text
    if not entities:
        return await _save_benign_state(session, raw_text, document_id)

    # ---------------------------------------------------------
    # STEP 2: RAG Verification (Suspicious Entities Only)
    # ---------------------------------------------------------
    suspicious_entities = [e for e in entities if e.get("is_suspicious")]
    verified_threats = {
        "is_known_threat": False,
        "matched_category": None,
        "reasoning": "No suspicious entities required RAG verification."
    }

    if suspicious_entities:
        ver_response = await verification_agent.arun(json.dumps(suspicious_entities))
        verified_threats = parse_agent_output(ver_response, VerificationResult)

    # ---------------------------------------------------------
    # STEP 3: Link & Topology Analysis
    # ---------------------------------------------------------
    link_payload = {
        "raw_text": raw_text,
        "canonical_entities": entities
    }
    link_response = await link_analysis_agent.arun(json.dumps(link_payload))
    network_edges = parse_agent_output(link_response, NetworkEdges).get("edges", [])

    # ---------------------------------------------------------
    # STEP 4: Deterministic Baseline Scoring
    # ---------------------------------------------------------
    baseline_score = 0.0
    baseline_score += len(suspicious_entities) * 15.0
    baseline_score += len(network_edges) * 5.0
    if verified_threats.get("is_known_threat"):
        baseline_score += 40.0

    baseline_score = min(baseline_score, 85.0)

    # ---------------------------------------------------------
    # STEP 5: Alerting & Final Synthesis
    # ---------------------------------------------------------
    alert_payload = {
        "baseline_calculated_score": baseline_score,
        "verified_threats": verified_threats,
        "edges": network_edges
    }
    alert_response = await alerting_agent.arun(json.dumps(alert_payload))
    final_alert = parse_agent_output(alert_response, AlertAnalysis)

    # ---------------------------------------------------------
    # STEP 6: PostgreSQL Persistence
    # ---------------------------------------------------------
    threat_state = ThreatState(
        document_id=document_id,
        raw_text=raw_text,
        extracted_entities=entities,
        sentiment_profile={
            "verified_match": verified_threats.get("matched_category"),
            "reasoning": final_alert.get("reasoning")
        },
        risk_score=final_alert.get("risk_score", baseline_score),
        status="READY"
    )
    session.add(threat_state)
    await session.flush()

    for edge in network_edges:
        parsed_ts = None
        ts_str = edge.get("timestamp")
        if ts_str:
            try:
                parsed_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        db_edge = NetworkEdge(
            threat_state_id=threat_state.id,
            source_node=edge["source_node"],
            target_node=edge["target_node"],
            interaction_type=edge["interaction_type"],
            interaction_timestamp=parsed_ts
        )
        session.add(db_edge)

    await session.commit()

    return {
        "status": "success",
        "threat_state_id": str(threat_state.id),
        "risk_score": threat_state.risk_score,
        "velocity_detected": final_alert.get("velocity_detected"),
        "extracted_entities_count": len(entities),
        "edges_mapped": len(network_edges)
    }

async def _save_benign_state(session: AsyncSession, text: str, doc_id: str) -> dict:
    threat_state = ThreatState(
        document_id=doc_id,
        raw_text=text,
        extracted_entities=[],
        sentiment_profile={"reasoning": "No entities detected; classified as benign."},
        risk_score=0.0,
        status="READY"
    )
    session.add(threat_state)
    await session.commit()
    return {
        "status": "success",
        "threat_state_id": str(threat_state.id),
        "risk_score": 0.0,
        "velocity_detected": False,
        "extracted_entities_count": 0,
        "edges_mapped": 0
    }

async def run_summarization_handoff(session: AsyncSession) -> dict:
    """
    Simulates the teammate's system pinging the database, picking up READY states,
    generating a human-readable intelligence brief, and closing the loop.
    """
    # 1. Ping the database for the oldest READY threat
    query = select(ThreatState).where(ThreatState.status == "READY").order_by(ThreatState.id).limit(1)
    result = await session.execute(query)
    threat = result.scalar_one_or_none()

    if not threat:
        return {"status": "idle", "message": "No pending threat states found."}

    # 2. Package the context for the Summarization Agent
    intel_context = {
        "threat_id": str(threat.id),
        "raw_text": threat.raw_text,
        "risk_score": threat.risk_score,
        "verified_match": threat.sentiment_profile.get("verified_match"),
        "reasoning": threat.sentiment_profile.get("reasoning")
    }

    # 3. Execute the Summarization Agent
    #summary_response = await summarization_agent.arun(json.dumps(intel_context))
    #final_brief = getattr(summary_response, "content", str(summary_response))

    final_brief = "MOCK SUMMARY: The detected threat involves predatory coercion targeting youth via the #MidnightWalk hashtag. Pipeline handoff successful."
    
    # 4. Update the database state to mark the pipeline complete
    threat.final_summary = final_brief
    threat.status = "COMPLETED"
    
    session.add(threat)
    await session.commit()

    return {
        "status": "success",
        "threat_id": str(threat.id),
        "new_status": threat.status,
        "final_summary": final_brief
    }