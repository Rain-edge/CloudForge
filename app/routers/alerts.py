"""Alertmanager Webhook 接收端点 — 演示环境验证告警链路。

告警流：PrometheusRule → Prometheus → Alertmanager → webhook → 本端点
收到告警后写入结构化日志（含 alertname/severity 等字段），
可在 Loki 检索 `event=alertmanager_webhook_received` 验证链路是否打通。

生产环境应把 values.alertmanager.webhookUrl 替换为企业微信/钉钉/飞书等真实接收端。
"""
import structlog
from fastapi import APIRouter, Request

logger = structlog.get_logger()

router = APIRouter(tags=["alerts"])


@router.post("/api/v1/alertmanager")
async def alertmanager_webhook(request: Request):
    """接收 Alertmanager webhook 告警并记录结构化日志。"""
    payload = await request.json()
    alerts = payload.get("alerts", [])

    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        logger.info(
            "alertmanager_webhook_received",
            alertname=labels.get("alertname", "unknown"),
            severity=labels.get("severity", "none"),
            status=alert.get("status", "firing"),
            summary=annotations.get("summary", ""),
        )

    return {"received": len(alerts)}
