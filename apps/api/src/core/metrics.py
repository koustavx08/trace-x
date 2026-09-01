"""Custom business metrics, on top of prometheus-fastapi-instrumentator's
auto-generated http_requests_total / http_request_duration_seconds (see
main.py). These three are what docker/grafana/dashboards/tracex-overview.json
already expects.
"""

from prometheus_client import Counter

investigations_total = Counter(
    "tracex_investigations_total",
    "Investigation runs by terminal status",
    ["status"],
)

wallet_analysis_total = Counter(
    "tracex_wallet_analysis_total",
    "Wallet analysis jobs by terminal status",
    ["status"],
)

ai_queries_total = Counter(
    "tracex_ai_queries_total",
    "AI assistant queries by classified type and answer confidence",
    ["query_type", "confidence"],
)
