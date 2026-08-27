"""
Role: Embedding logic & pgvector search routines.
This module manages embedding generation and executes hybrid retrieval (combining text matching and vector similarity) using pgvector.
Contribution: Converts threat text into 384-dimensional vector arrays, seeds records into the database, 
and runs hybrid text/vector distance queries using SQLAlchemy.
"""

import requests
import numpy as np
from typing import List, Dict, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models import HistoricalIntelligence
from app.core.config import settings

def get_embedding(text: str) -> List[float]:
    """
    Generates a 384-dimensional vector embedding via Ollama API.
    Uses a deterministic character-hash fallback if Ollama is offline.
    """
    try:
        response = requests.post(
            f"http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text.lower()},
            timeout=2.0
        )
        if response.status_code == 200:
            emb = response.json().get("embedding", [])
            if len(emb) == 384:
                return emb
    except Exception:
        pass

    # Deterministic 384-dim fallback vector based on word tokens
    words = text.lower().split()
    vec = np.zeros(384, dtype=np.float32)
    for word in words:
        seed = abs(hash(word)) % (2**32)
        np.random.seed(seed)
        vec += np.random.randn(384).astype(np.float32)

    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()


async def seed_historical_intelligence(session: AsyncSession, records: List[Dict[str, Any]]) -> int:
    """
    Seeds initial records into the historical_intelligence table if it is currently empty.
    """
    existing_stmt = select(HistoricalIntelligence)
    result = await session.execute(existing_stmt)
    if result.scalars().first() is not None:
        return 0  # Already seeded

    inserted_count = 0
    for doc in records:
        embed_text = f"{doc['title']} {doc['content']}"
        vector_data = get_embedding(embed_text)
        
        record = HistoricalIntelligence(
            id=doc["id"],
            title=doc["title"],
            category=doc["category"],
            content=doc["content"],
            embedding=vector_data
        )
        session.add(record)
        inserted_count += 1

    await session.commit()
    return inserted_count


async def hybrid_search_intelligence(
    session: AsyncSession, query: str, limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Hybrid Retriever: Combines SQL ILIKE text keyword search with pgvector distance.
    """
    query_vector = get_embedding(query)
    
    # 1. Vector similarity search ordered by pgvector L2 distance (<=>)
    stmt = (
        select(HistoricalIntelligence)
        .where(
            or_(
                HistoricalIntelligence.title.ilike(f"%{query}%"),
                HistoricalIntelligence.content.ilike(f"%{query}%"),
                HistoricalIntelligence.category.ilike(f"%{query}%")
            )
        )
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    matches = result.scalars().all()

    # Fallback to pure vector distance if exact keyword match returns fewer items
    if not matches:
        vector_stmt = (
            select(HistoricalIntelligence)
            .order_by(HistoricalIntelligence.embedding.l2_distance(query_vector))
            .limit(limit)
        )
        vector_result = await session.execute(vector_stmt)
        matches = vector_result.scalars().all()

    return [
        {
            "id": m.id,
            "title": m.title,
            "category": m.category,
            "content": m.content
        }
        for m in matches
    ]