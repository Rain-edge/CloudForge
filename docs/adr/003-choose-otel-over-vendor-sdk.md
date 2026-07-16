# ADR-003: Use OpenTelemetry over vendor-specific SDKs

## Status
Accepted

## Context
The project needs distributed tracing and metrics instrumentation. Options include vendor-specific SDKs (Datadog, New Relic, Sentry) or OpenTelemetry as a vendor-neutral standard.

## Decision
Use **OpenTelemetry** (OTel) with **OTLP exporter**, backed by **Tempo** (traces), **Prometheus** (metrics), and **Loki** (logs).

## Rationale
1. **Vendor neutrality**: OTel is a CNCF incubating project and the emerging industry standard. Demonstrating OTel proficiency is more valuable than lock-in to any single vendor's SDK.
2. **Unified instrumentation**: One SDK provides Traces + Metrics + Logs correlation via a single set of auto-instrumentation libraries. No need to wire three different SDKs.
3. **Interview signal**: OTel adoption is accelerating rapidly. Understanding W3C Trace Context propagation, span attributes, and resource detection shows cloud-native maturity.
4. **Local development**: The OTLP exporter can target Jaeger (local) or Tempo (K8s) without code changes — only an environment variable switch.

## Tradeoffs
- **Learning curve**: OTel has a steeper initial learning curve than adding `@sentry/fastapi` or `dd-trace`. The auto-instrumentation libraries sometimes produce noisy or incomplete spans.
- **Mitigation**: Start with console exporter for local debugging. Add OTLP exporter only after spans are verified correct. Document the OTel setup as a reusable pattern.

## Consequences
- `app/core/telemetry.py` configures OTel SDK with auto-instrumentation for FastAPI and SQLAlchemy
- OTLP exporter targets Tempo (or Jaeger via env var for local dev)
- Trace IDs are injected into structured logs via `trace_id` for Loki correlation
