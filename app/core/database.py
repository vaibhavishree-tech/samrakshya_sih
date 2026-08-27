"""
Configures asynchronous session management.
It creates the create_async_engine, defines the AsyncSessionLocal session generator, 
and initializes Base = declarative_base(), which registers all database tables.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine for PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Session factory for DB dependency injection
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# SQLAlchemy declarative base
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session