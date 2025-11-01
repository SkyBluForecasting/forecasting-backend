"""Database client for SQLAlchemy async sessions."""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

logger.info(f"Initializing database engine for: {DATABASE_URL}")


# ------------------------------------------------------------
# Engine creation helper
# ------------------------------------------------------------
def make_engine(database_url: str):
    """Create an async SQLAlchemy engine with appropriate settings."""
    if not database_url.startswith("sqlite"):
        # Use connection pooling for Postgres or other production databases
        return create_async_engine(
            database_url,
            echo=False,
            future=True,
            pool_size=20,
            max_overflow=40,
            pool_timeout=60,
            pool_recycle=1800,
        )
    else:
        # Simplified config for SQLite (especially in CI)
        return create_async_engine(
            database_url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )


# ------------------------------------------------------------
# Engine & Session factory
# ------------------------------------------------------------
engine = make_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


# ------------------------------------------------------------
# Declarative base
# ------------------------------------------------------------
class Base(DeclarativeBase):
    """Define the declarative base class for SQLAlchemy models."""

    pass


# ------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------
async def get_db() -> AsyncSession:
    """Yield an async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db_pool():
    """Dispose the SQLAlchemy async engine to close all connections."""
    await engine.dispose()
