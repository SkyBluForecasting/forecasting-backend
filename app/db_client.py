"""Database client for SQLAlchemy async sessions."""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load environment variables from .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Async SQLAlchemy engine
# Add pooling only for non-SQLite databases
if not DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_size=20,
        max_overflow=40,
        pool_timeout=60,
        pool_recycle=1800,
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
    )

# Async session factory
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Define the declarative base class for SQLAlchemy models."""

    pass


async def get_db() -> AsyncSession:
    """Yield an async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db_pool():
    """Dispose the SQLAlchemy async engine to close all connections."""
    await engine.dispose()
