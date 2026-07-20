"""
Prometheus 指标暴露 — 使用 prometheus-fastapi-instrumentator 自动采集。
===========================================================================
本文件在 /metrics 端点暴露 Prometheus 格式的 HTTP 请求指标，包括：

  指标名称                              说明
  ─────────────────────────────────────────────────────────────
  http_requests_total                  请求总数（可按 method, status, handler 分组）
  http_request_size_bytes              请求体大小分布
  http_response_size_bytes             响应体大小分布
  http_request_duration_seconds        请求延迟直方图（p50/p95/p99）
  http_requests_inprogress             当前进行中的请求数

Dashboard 和 PrometheusRule 中的 PromQL 查询依赖这些指标。
状态码分组已关闭（should_group_status_codes=False），使得
status="200"、status=~"5.." 等过滤器能正确工作。

配置说明：
  - should_group_status_codes=False → 状态码保持原值（"200"/"404"/"500"）
                                      Dashboard 可按具体状态码或正则分组
  - should_ignore_untemplated=True  → 忽略非模板化路由（如 /metrics 自身）
  - should_instrument_requests_inprogress=True → 暴露正在处理的请求数（用于 HPA 自定义指标）
"""
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app):
    """为 FastAPI 应用注册 Prometheus 指标采集和 /metrics 端点。

    Args:
        app: FastAPI 应用实例
    """
    # 创建独立的指标注册表，避免与系统默认 registry 冲突
    registry = CollectorRegistry(auto_describe=True)

    # 配置自动插桩器
    instrumentator = Instrumentator(
        registry=registry,
        # ★ 关键：不合并状态码，保留 "200"/"404"/"500" 原值
        #    这样 Dashboard 的 status=~"5.." 过滤和 PrometheusRule 告警才能生效
        should_group_status_codes=False,
        # 忽略非模板化路由（/metrics 自身、/docs 等）
        should_ignore_untemplated=True,
        # 暴露当前进行中的请求数（Gauge 类型，HPA 可能用到）
        should_instrument_requests_inprogress=True,
        # 延迟直方图保留 2 位小数，减少时间序列数量
        should_round_latency_decimals=True,
    )

    # instrument(app) 为所有路由注册中间件，expose 在 /metrics 端点暴露指标
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
