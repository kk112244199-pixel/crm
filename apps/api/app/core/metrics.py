"""
Prometheus metrics — /metrics 端点
P4: stub counters + histograms（prometheus_client 已在 requirements.txt）
Phase 2: 接入 Grafana Cloud / 自建 Prometheus
"""
from __future__ import annotations
from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
from prometheus_client import multiprocess, CollectorRegistry
import time

# ── Metrics definitions ───────────────────────────────────────────────────────

llm_requests_total = Counter(
    "montocrm_llm_requests_total",
    "Total LLM API calls",
    ["agent", "provider", "model", "status"],
)

llm_latency_seconds = Histogram(
    "montocrm_llm_latency_seconds",
    "LLM API call latency",
    ["agent", "provider"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

http_requests_total = Counter(
    "montocrm_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

http_latency_seconds = Histogram(
    "montocrm_http_latency_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0],
)

pending_actions_total = Gauge(
    "montocrm_pending_actions_total",
    "Current pending actions count",
    ["status"],
)

health_score_gauge = Histogram(
    "montocrm_opportunity_health_score",
    "Distribution of opportunity health scores",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

guard_blocked_total = Counter(
    "montocrm_guard_blocked_total",
    "LLM Guard blocked requests",
    ["reason"],
)

rag_chunks_retrieved = Histogram(
    "montocrm_rag_chunks_retrieved",
    "RAG chunks retrieved per query",
    buckets=[0, 1, 2, 5, 10, 20],
)


# ── Helper decorators / context managers ─────────────────────────────────────

class LLMTimer:
    """Context manager that records LLM latency + request count."""
    def __init__(self, agent: str, provider: str, model: str):
        self.agent = agent
        self.provider = provider
        self.model = model
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency = time.perf_counter() - self._t0
        status = "error" if exc_type else "ok"
        llm_requests_total.labels(
            agent=self.agent, provider=self.provider,
            model=self.model, status=status,
        ).inc()
        llm_latency_seconds.labels(
            agent=self.agent, provider=self.provider,
        ).observe(latency)
        return False  # don't suppress exceptions


def get_metrics_output() -> bytes:
    return generate_latest(REGISTRY)
