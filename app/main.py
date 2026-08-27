"""
Main FastAPI Application Entry Point for Sāmarakṣya OSINT Engine.
"""

from app.agents.supervisor import run_summarization_handoff
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal, get_db
from app.rag.seed_data import INITIAL_THREAT_RECORDS
from app.rag.vector_store import seed_historical_intelligence
from app.rag.tools import retrieve_threat_context
from app.agents.supervisor import process_threat_pipeline
import app.core.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Enable pgvector & create SQL tables
    async with engine.begin() as conn:
        print("⏳ Enabling pgvector extension & building PostgreSQL schemas...", flush=True)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)

    # 2. Seed historical threat intelligence vector store
    async with AsyncSessionLocal() as session:
        count = await seed_historical_intelligence(session, INITIAL_THREAT_RECORDS)
        if count > 0:
            print(f"✅ Seeded {count} threat intelligence records into PostgreSQL.", flush=True)
        else:
            print("✅ PostgreSQL Vector Store already initialized.", flush=True)

    yield

# --- THE APP INSTANCE UCK/UVICORN LOOKS FOR ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Payload Schema for Analysis Endpoint
class ThreatAnalysisRequest(BaseModel):
    raw_text: str = Field(..., description="Raw chaotic text payload from Telegram, X, or OSINT feeds")
    document_id: str = Field(None, description="Optional UUID link to raw_osint_documents table")

@app.get("/")
def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "database": "postgresql"
    }

@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {"status": "healthy", "database": "postgresql_connected"}

@app.get(f"{settings.API_V1_STR}/rag/search")
async def search_rag(query: str = Query(..., description="Entity or keyword to search in threat DB")):
    """
    Diagnostic endpoint to test PostgreSQL Vector Store directly.
    """
    result = retrieve_threat_context(query)
    return {"query": query, "retrieved_context": result}

@app.post(f"{settings.API_V1_STR}/analyze")
async def analyze_threat_payload(
    payload: ThreatAnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Main Agentic Orchestration Endpoint.
    Ingests raw OSINT text, executes the 4-agent pipeline, and commits state to PostgreSQL.
    """
    try:
        result = await process_threat_pipeline(
            raw_text=payload.raw_text,
            session=db,
            document_id=payload.document_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")

@app.post(f"{settings.API_V1_STR}/synthesize")
async def trigger_synthesis(db: AsyncSession = Depends(get_db)):
    """
    Handoff Endpoint: Pings the DB for READY states and generates final summaries.
    """
    try:
        result = await run_summarization_handoff(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Handoff execution error: {str(e)}")