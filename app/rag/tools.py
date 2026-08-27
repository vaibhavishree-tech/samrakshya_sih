"""
This module provides the clean tool function that agents invoke during execution.
Agno/LLM compatible RAG tool functions for verification.
"""

from app.core.database import AsyncSessionLocal
from app.rag.vector_store import hybrid_search_intelligence

async def retrieve_threat_context(query: str) -> str:
    """
    RAG Retrieval Tool: Queries PostgreSQL historical_intelligence using hybrid search
    (exact keyword ILIKE + pgvector distance) to retrieve historical OSINT context.

    Args:
        query (str): The entity name, hashtag, or text segment to verify.

    Returns:
        str: Formatted historical intelligence matches for LLM evaluation.
    """
    async with AsyncSessionLocal() as session:
        matches = await hybrid_search_intelligence(session, query, limit=3)

    if not matches:
        return "No historical threat matches found in PostgreSQL RAG database."

    context_blocks = []
    for idx, match in enumerate(matches, 1):
        context_blocks.append(
            f"Match #{idx} [{match['category']}]: {match['title']}\n"
            f"Details: {match['content']}"
        )

    return "\n\n".join(context_blocks)