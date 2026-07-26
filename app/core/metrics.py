"""Prometheus 指标暴露 — prometheus-fastapi-instrumentator 自动采集。

/metrics 端点暴露 HTTP 请求计数、延迟直方图与进行中请求数，
供 Grafana Dashboard 与 PrometheusRule 告警查询。
"""
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app):
    """为 FastAPI 注册自动插桩并暴露 /metrics 端点。"""
    # 独立 registry，避免与系统默认 registry 冲突
    registry = CollectorRegistry(auto_describe=True)

    instrumentator = Instrumentator(
        registry=registry,
        # 保留状态码原值（"200"/"404"/"500"），使 status=~"5.." 等过滤器生效
        should_group_status_codes=False,
        should_ignore_untemplated=True,              # 忽略 /metrics、/docs 等非模板路由
        should_instrument_requests_inprogress=True,  # 暴露当前进行中请求数（Gauge）
        should_round_latency_decimals=True,         # 延迟保留 2 位小数，降低时序基数
    )

    instrumentator.instrument(app).expose(app, endpoint="/metrics")
