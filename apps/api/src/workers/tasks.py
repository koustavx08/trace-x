"""
Background task definitions for async processing.
"""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog
from celery import shared_task

from src.core import get_session_context
from src.core.metrics import investigations_total, wallet_analysis_total
from src.intelligence import entity_intelligence
from src.models import InvestigationRun, InvestigationStatus
from src.reports import report_generator

from ..analytics import risk_scoring_engine
from ..graph.models import ConfidenceLevel, EntityType, GraphEntity, GraphTransaction, GraphWallet
from ..graph.repository import graph_repository

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run async coroutine in Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def wallet_analysis_task(self, wallet_id: str, trace_depth: int = 5, max_transactions: int = 1000):
    """Background task for wallet analysis."""

    async def _analyze():
        async with get_session_context() as session:
            from src.models import Transaction, Wallet

            wallet = await session.get(Wallet, UUID(wallet_id))
            if not wallet:
                logger.error("wallet_not_found", wallet_id=wallet_id)
                return {"status": "failed", "error": "Wallet not found"}

            # Update status
            investigation = InvestigationRun(
                case_id=wallet.case_id,
                wallet_id=wallet.id,
                status=InvestigationStatus.RUNNING,
                config={"trace_depth": trace_depth, "max_transactions": max_transactions},
            )
            session.add(investigation)
            await session.flush()

            try:
                # Fetch transactions from blockchain
                from ..core.validation import get_chain_id_by_name
                from ..providers import ProviderFactory

                ProviderFactory.initialize()
                chain_id = get_chain_id_by_name(wallet.chain) or 1
                provider = ProviderFactory.get_provider(chain_id)

                if not provider:
                    raise ValueError(f"No provider for chain: {wallet.chain}")

                transactions = await provider.get_transactions_by_address(
                    wallet.address,
                    page=1,
                    page_size=max_transactions,
                )

                # Store transactions
                graph_transactions = []
                for tx in transactions:
                    db_tx = Transaction(
                        wallet_id=wallet.id,
                        tx_hash=tx.tx_hash,
                        block_number=tx.block_number,
                        timestamp=tx.timestamp,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        value=tx.value,
                        value_usd=tx.value_usd,
                        token_address=tx.token_address,
                        token_symbol=tx.token_symbol,
                        method=tx.method,
                        is_suspicious=False,
                        transaction_metadata=tx.metadata,
                    )
                    session.add(db_tx)
                    graph_transactions.append(tx)

                # Sync to Neo4j
                graph_wallet = GraphWallet(
                    address=wallet.address,
                    chain=wallet.chain,
                    label=wallet.label,
                    risk_score=float(wallet.risk_score),
                    first_seen=wallet.created_at,
                    last_seen=wallet.updated_at,
                    tx_count=len(transactions),
                    metadata={"source": "background_analysis"},
                )
                await graph_repository.upsert_wallet(graph_wallet)

                for tx in graph_transactions:
                    graph_tx = GraphTransaction(
                        tx_hash=tx.tx_hash,
                        chain=wallet.chain,
                        block_number=tx.block_number,
                        timestamp=tx.timestamp,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        value=tx.value,
                        value_usd=tx.value_usd,
                        token_address=tx.token_address,
                        token_symbol=tx.token_symbol,
                        method=tx.method,
                        is_suspicious=tx.is_suspicious,
                        metadata=tx.metadata,
                    )
                    await graph_repository.upsert_transaction(graph_tx)
                    await graph_repository.link_wallet_transaction(
                        wallet.address, wallet.chain, tx.tx_hash, "sent"
                    )
                    await graph_repository.link_wallet_transaction(
                        tx.to_address, wallet.chain, tx.tx_hash, "received"
                    )

                # Entity enrichment
                await entity_intelligence.enrich_wallet(wallet.address, wallet.chain)

                # Risk assessment
                graph_context = {}
                try:
                    from ..graph.queries import graph_queries

                    graph_context[
                        "mixer_interactions"
                    ] = await graph_queries.find_mixer_interactions(
                        wallet.address, wallet.chain, max_hops=4
                    )
                    graph_context["peel_chains"] = await graph_queries.detect_peel_chains(
                        chain=wallet.chain
                    )
                except Exception as e:
                    logger.warning("graph_context_failed", error=str(e))

                entity_data = None
                if wallet.entity_name:
                    entity_data = {
                        "entity_name": wallet.entity_name,
                        "entity_type": wallet.entity_type,
                        "confidence": wallet.entity_confidence,
                    }

                assessment = await risk_scoring_engine.assess_wallet(
                    wallet=graph_wallet,
                    transactions=graph_transactions,
                    entity_data=entity_data,
                    graph_context=graph_context,
                )

                # Update wallet with risk score
                wallet.risk_score = assessment.overall_score
                wallet.wallet_metadata = wallet.wallet_metadata or {}
                wallet.wallet_metadata["risk_factors"] = [
                    {
                        "type": f.factor_type.value,
                        "severity": f.severity.value,
                        "description": f.description,
                    }
                    for f in assessment.factors
                ]

                # Complete investigation
                investigation.status = InvestigationStatus.COMPLETED
                investigation.completed_at = datetime.utcnow()
                investigation.result_summary = {
                    "transactions_found": len(transactions),
                    "unique_addresses": len(
                        set(
                            [tx.from_address for tx in graph_transactions]
                            + [tx.to_address for tx in graph_transactions]
                        )
                    ),
                    "total_value_eth": str(
                        sum(int(tx.value) for tx in graph_transactions if tx.value.isdigit())
                    ),
                    "risk_assessment": assessment.to_dict(),
                    "chains_analyzed": [wallet.chain],
                }

                await session.commit()
                investigations_total.labels(status="completed").inc()
                wallet_analysis_total.labels(status="completed").inc()

                logger.info(
                    "wallet_analysis_completed",
                    wallet_id=wallet_id,
                    investigation_id=str(investigation.id),
                )
                return {
                    "status": "completed",
                    "investigation_id": str(investigation.id),
                    "transactions_analyzed": len(transactions),
                    "risk_score": assessment.overall_score,
                }

            except Exception as e:
                investigation.status = InvestigationStatus.FAILED
                investigation.error_message = str(e)
                investigation.completed_at = datetime.utcnow()
                investigations_total.labels(status="failed").inc()
                wallet_analysis_total.labels(status="failed").inc()
                await session.commit()

                logger.error("wallet_analysis_failed", wallet_id=wallet_id, error=str(e))
                raise self.retry(exc=e) from e

    return run_async(_analyze())


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def report_generation_task(
    self,
    case_id: str,
    investigation_run_id: str | None = None,
    title: str | None = None,
    template: str = "technical_findings",
    format: str = "pdf",
    generated_by: str = "system",
):
    """Background task for report generation."""

    async def _generate():
        async with get_session_context() as session:
            from src.models import Case

            case = await session.get(Case, UUID(case_id))
            if not case:
                raise ValueError(f"Case not found: {case_id}")

            report_title = title or f"{case.title} - Investigation Report"

            report = await report_generator.generate_report(
                case_id=case_id,
                investigation_run_id=investigation_run_id,
                title=report_title,
                template=template,
                format=format,
                generated_by=generated_by,
            )

            # Save report to database
            from src.models import Report

            db_report = Report(
                case_id=UUID(case_id),
                investigation_run_id=UUID(investigation_run_id) if investigation_run_id else None,
                title=report.title,
                summary=report.sections[0].content[:500] if report.sections else "",
                findings={
                    "sections": [{"title": s.title, "order": s.order} for s in report.sections],
                },
                risk_assessment={},
                graph_snapshot={},
                generated_by=UUID(generated_by)
                if generated_by != "system"
                else UUID("00000000-0000-0000-0000-000000000000"),
                format=format,
            )
            session.add(db_report)
            await session.commit()

            logger.info("report_generated", report_id=str(db_report.id), case_id=case_id)
            return {
                "status": "completed",
                "report_id": str(db_report.id),
                "file_size": len(report.file_content) if report.file_content else 0,
            }

    return run_async(_generate())


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def graph_sync_task(self, wallet_id: str):
    """Background task to sync wallet data to Neo4j."""

    async def _sync():
        async with get_session_context() as session:
            from sqlalchemy import select

            from src.models import Transaction, Wallet

            wallet = await session.get(Wallet, UUID(wallet_id))
            if not wallet:
                raise ValueError(f"Wallet not found: {wallet_id}")

            # Create graph wallet
            graph_wallet = GraphWallet(
                address=wallet.address,
                chain=wallet.chain,
                label=wallet.label,
                risk_score=float(wallet.risk_score),
                first_seen=wallet.created_at,
                last_seen=wallet.updated_at,
                entity_name=wallet.entity_name,
                entity_type=EntityType(wallet.entity_type) if wallet.entity_type else None,
                entity_confidence=ConfidenceLevel(wallet.entity_confidence)
                if wallet.entity_confidence
                else ConfidenceLevel.UNKNOWN,
            )
            await graph_repository.upsert_wallet(graph_wallet)

            # Sync transactions
            result = await session.execute(
                select(Transaction).where(Transaction.wallet_id == wallet.id)
            )
            transactions = result.scalars().all()

            for tx in transactions:
                graph_tx = GraphTransaction(
                    tx_hash=tx.tx_hash,
                    chain=wallet.chain,
                    block_number=tx.block_number,
                    timestamp=tx.timestamp,
                    from_address=tx.from_address,
                    to_address=tx.to_address,
                    value=tx.value,
                    value_usd=tx.value_usd,
                    token_address=tx.token_address,
                    token_symbol=tx.token_symbol,
                    method=tx.method,
                    is_suspicious=tx.is_suspicious,
                    metadata=tx.transaction_metadata or {},
                )
                await graph_repository.upsert_transaction(graph_tx)
                await graph_repository.link_wallet_transaction(
                    wallet.address, wallet.chain, tx.tx_hash, "sent"
                )
                await graph_repository.link_wallet_transaction(
                    tx.to_address, wallet.chain, tx.tx_hash, "received"
                )

            if wallet.entity_name and wallet.entity_confidence:
                entity = GraphEntity(
                    name=wallet.entity_name,
                    entity_type=EntityType(wallet.entity_type)
                    if wallet.entity_type
                    else EntityType.UNKNOWN,
                    address=wallet.address,
                    chain=wallet.chain,
                    confidence=ConfidenceLevel(wallet.entity_confidence),
                    source="analysis",
                )
                await graph_repository.upsert_entity(entity)
                await graph_repository.link_wallet_entity(
                    wallet.address, wallet.chain, wallet.address
                )

            # Entity enrichment
            await entity_intelligence.enrich_wallet(wallet.address, wallet.chain)

            logger.info("graph_sync_completed", wallet_id=wallet_id, transactions=len(transactions))
            return {"status": "completed", "transactions_synced": len(transactions)}

    return run_async(_sync())


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def entity_enrichment_task(self, wallet_id: str):
    """Background task for entity enrichment."""

    async def _enrich():
        async with get_session_context() as session:
            from src.models import Wallet

            wallet = await session.get(Wallet, UUID(wallet_id))
            if not wallet:
                raise ValueError(f"Wallet not found: {wallet_id}")

            entity = await entity_intelligence.enrich_wallet(wallet.address, wallet.chain)

            if entity:
                wallet.entity_name = entity.name
                wallet.entity_type = entity.entity_type.value
                wallet.entity_confidence = entity.confidence.value
                wallet.attribution_status = "attributed"
                await session.commit()

                logger.info("entity_enriched", wallet_id=wallet_id, entity=entity.name)
                return {
                    "status": "completed",
                    "entity": entity.name,
                    "confidence": entity.confidence.value,
                }
            else:
                logger.info("no_entity_found", wallet_id=wallet_id)
                return {"status": "completed", "entity": None}

    return run_async(_enrich())


@shared_task
def periodic_entity_sync():
    """Periodic task to sync entity intelligence to Neo4j."""

    async def _sync():
        stats = await entity_intelligence.sync_to_graph()
        logger.info("periodic_entity_sync_completed", stats=stats)
        return stats

    return run_async(_sync())


@shared_task
def cleanup_stale_investigations():
    """Clean up investigations stuck in running state for too long."""

    async def _cleanup():
        async with get_session_context() as session:
            from datetime import timedelta

            from sqlalchemy import select

            cutoff = datetime.utcnow() - timedelta(hours=24)

            result = await session.execute(
                select(InvestigationRun).where(
                    InvestigationRun.status == InvestigationStatus.RUNNING,
                    InvestigationRun.started_at < cutoff,
                )
            )
            stale = result.scalars().all()

            count = 0
            for inv in stale:
                inv.status = InvestigationStatus.FAILED
                inv.error_message = "Investigation timed out (stale for >24 hours)"
                inv.completed_at = datetime.utcnow()
                count += 1

            await session.commit()

            logger.info("cleanup_stale_investigations_completed", count=count)
            return {"status": "completed", "cleaned": count}

    return run_async(_cleanup())
