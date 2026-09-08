# ADR-003: 用 OpenTelemetry 而不是厂商 SDK

## 状态
已接受

## 背景
项目要做分布式追踪和指标采集。可选：厂商 SDK（Datadog、New Relic、Sentry 等），或者 OpenTelemetry 这种厂商中立的标准。

## 决策
用 **OpenTelemetry**，通过 **OTLP** 导出，后端是 **Tempo**（链路）、**Prometheus**（指标）、**Loki**（日志）。

## 理由
1. **厂商中立**：OTel 是 CNCF incubating 项目，是业界标准方向，不绑定任何一家厂商
2. **一套 SDK 搞定三支柱**：Traces + Metrics + Logs 用同一套自动埋点库，不用接三家 SDK
3. **开发调试方便**：OTLP exporter 可以指向 Jaeger（本地）或 Tempo（K8s），只改环境变量，不动代码
4. **W3C Trace Context 标准**：trace_id 能进结构化日志，实现日志和链路关联

## 权衡
- **学习成本**：OTel 上手比直接加 @sentry/fastapi 或 dd-trace 陡，自动埋点库偶尔会产生噪音 span
- **处理**：先在本地用 console exporter 调试，span 确认正确后再开 OTLP；OTel 配置写成可复用的模式

## 结果
- app/core/telemetry.py 配置 OTel SDK，对 FastAPI 和 SQLAlchemy 自动埋点
- OTLP exporter 指向 Tempo（本地开发通过环境变量切到 Jaeger）
- trace_id 注入结构化日志，Loki 里能直接关联到 Tempo 调用链
