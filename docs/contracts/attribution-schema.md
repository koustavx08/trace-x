# VASP Attribution Schema

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/analytics/attribution_engine.py` and
> `apps/api/src/api/v1/risk.py`.

## Purpose

Attribution answers "which known entity (exchange, mixer, bridge, DeFi protocol...) did funds from this wallet end up
at, and how confident are we?" It builds on top of `graph-schema.md`'s path-finding.

## `AttributionType`

```
DIRECT     — path length 1, or CONFIRMED entity within 2 hops
INDIRECT   — multi-hop path to an EXCHANGE or BRIDGE entity
CLUSTER    — (defined, not currently produced by _determine_attribution_type's branches)
HEURISTIC  — path to a DEFI entity
```
`CLUSTER` is a defined `AttributionType` value with a weight in `ATTRIBUTION_WEIGHTS` (0.6) but
`_determine_attribution_type` has no branch that returns it — every non-DIRECT/INDIRECT/HEURISTIC case currently falls
through to `INDIRECT`. Effectively unreachable in the baseline logic; worth flagging if cluster-based attribution is
expected to ship.

## `AttributionEvidence`

```python
source: str            # e.g. "graph_traversal", "entity_registry", "manual_verification"
evidence_type: str      # e.g. "on_chain_path", "off_chain_intelligence", "verified_attribution"
description: str
confidence: ConfidenceLevel
data: dict
```
Every attribution accumulates at least 2 evidence items: one `graph_traversal`/`on_chain_path` (the fund-flow path
itself) and one `entity_registry`/`off_chain_intelligence` (the known-entity record). A third `manual_verification`
item is added only when the target entity's confidence is already `CONFIRMED`.

## `VASPAttribution`

```python
entity_name: str
entity_type: EntityType
address: str
chain: str
attribution_type: AttributionType
confidence: ConfidenceLevel
confidence_score: float          # 0.0–1.0, see formula below
distance_hops: int
total_value_eth: float
evidence: list[AttributionEvidence]
path: GraphPath | None
attributed_at: datetime
```

## Confidence downgrade table (`_calculate_confidence`)

Confidence starts at the target entity's own registry confidence and degrades with path length:

| Entity confidence | ≤2 hops | ≤3-4 hops | >4 hops |
|---|---|---|---|
| CONFIRMED | CONFIRMED (if DIRECT & ≤2) else HIGH_CONFIDENCE (≤4) | HIGH_CONFIDENCE | PROBABLE |
| HIGH_CONFIDENCE | HIGH_CONFIDENCE (≤3) | PROBABLE | PROBABLE |
| PROBABLE | PROBABLE (≤2) | UNKNOWN | UNKNOWN |
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## Confidence score formula (`_calculate_confidence_score`)

```
base_score   = CONFIDENCE_SCORES[confidence]        # CONFIRMED=1.0, HIGH_CONFIDENCE=0.85, PROBABLE=0.65, UNKNOWN=0.3
path_penalty = max(0, 1 - (path.length - 1) * 0.1)   # -10% per hop beyond the first
type_weight  = ATTRIBUTION_WEIGHTS[attribution_type]  # DIRECT=1.0, INDIRECT=0.8, CLUSTER=0.6, HEURISTIC=0.4
value_factor = min(1.0, total_value_eth / 10.0) if total_value_eth > 0 else 0.5

confidence_score = clamp(base_score * path_penalty * type_weight * (0.7 + 0.3 * value_factor), 0.0, 1.0)
```

## Attribution flow (`AttributionEngine.attribute_wallet`)

1. `graph_repository.find_paths_to_entities(start_address, chain, entity_types=[EXCHANGE, BRIDGE, DEFI], max_depth,
   min_confidence=PROBABLE, limit=20)`.
2. For each path with a resolved `endpoint_entity`, build a `VASPAttribution` via `_create_attribution`.
3. Sort by `(-confidence_score, distance_hops)` — highest confidence first, ties broken by fewest hops.
4. Return top 10.

Note `MIXER` is deliberately excluded from the `entity_types` searched here (attribution targets legitimate VASPs);
mixer detection is a separate risk factor (`risk-schema.md`), not an attribution outcome.

## `get_attribution_summary`

Wraps `attribute_wallet` into a UI-friendly summary: `{attributed: bool, nearest_vasp: {...} | None,
all_attributions: [...], summary: {exchanges_found, mixers_found, bridges_found, highest_confidence, average_hops}}`.
Note `mixers_found` will always be `0` given point 4 above (mixers are never in the searched `entity_types`) — this
looks like dead/vestigial code in the summary construction, not a bug that changes output correctness, just a
statistic that can never be non-zero via this path.

## API surface

- `GET /risk/wallets/{wallet_id}/attribution` → `get_attribution_summary` result (`AttributionResponse`).
- `POST /risk/wallets/{wallet_id}/attribute` → raw `list[VASPAttribution.to_dict()]` (up to 10), no summary wrapper.
