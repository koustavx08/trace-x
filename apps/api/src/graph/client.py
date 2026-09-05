from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession, Record
from neo4j.exceptions import Neo4jError

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Neo4jClient:
    _driver: AsyncDriver | None = None

    @classmethod
    async def initialize(cls) -> None:
        if cls._driver is not None:
            return
        cls._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
            connection_timeout=30,
        )
        await cls._driver.verify_connectivity()
        await cls._create_indexes()
        logger.info("neo4j_client_initialized", uri=settings.NEO4J_URI)

    @classmethod
    async def _create_indexes(cls) -> None:
        async with cls.session() as session:
            indexes = [
                "CREATE INDEX wallet_address_chain IF NOT EXISTS FOR (w:Wallet) ON (w.address, w.chain)",
                "CREATE INDEX wallet_entity IF NOT EXISTS FOR (w:Wallet) ON (w.entity_name)",
                "CREATE INDEX tx_hash IF NOT EXISTS FOR (t:Transaction) ON (t.tx_hash)",
                "CREATE INDEX tx_from IF NOT EXISTS FOR (t:Transaction) ON (t.from_address)",
                "CREATE INDEX tx_to IF NOT EXISTS FOR (t:Transaction) ON (t.to_address)",
                "CREATE INDEX entity_address_chain IF NOT EXISTS FOR (e:Entity) ON (e.address, e.chain)",
                "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            ]
            for idx in indexes:
                try:
                    await session.run(idx)
                except Neo4jError as e:
                    logger.warning("index_creation_failed", index=idx, error=str(e))

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[AsyncSession, None]:
        if cls._driver is None:
            await cls.initialize()
        assert cls._driver is not None
        async with cls._driver.session() as session:
            yield session

    @classmethod
    async def close(cls) -> None:
        if cls._driver:
            await cls._driver.close()
            cls._driver = None
            logger.info("neo4j_client_closed")

    @classmethod
    async def execute_query(
        cls, query: str, parameters: dict[str, Any] | None = None
    ) -> list[Record]:
        async with cls.session() as session:
            result = await session.run(query, parameters or {})
            return [record async for record in result]

    @classmethod
    async def execute_write(cls, query: str, parameters: dict[str, Any] | None = None) -> Any:
        async with cls.session() as session:
            result = await session.execute_write(lambda tx: tx.run(query, parameters or {}))
            return [record async for record in result]

    @classmethod
    async def execute_transaction(cls, queries: list[tuple[str, dict[str, Any]]]) -> list[Any]:
        async with cls.session() as session:

            async def _run_tx(tx):
                results = []
                for query, params in queries:
                    result = await tx.run(query, params)
                    results.append([record async for record in result])
                return results

            return await session.execute_write(_run_tx)
