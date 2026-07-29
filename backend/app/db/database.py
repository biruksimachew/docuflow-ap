from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


async def check_database() -> bool:
    """Confirm that PostgreSQL accepts a simple query."""

    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        return result.scalar_one() == 1
