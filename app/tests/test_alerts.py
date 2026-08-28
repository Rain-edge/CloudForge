"""Alertmanager webhook 接收端点测试。"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_alertmanager_webhook_accepts_alerts(client: AsyncClient):
    """POST 告警负载应返回 200 并回显接收数量。"""
    resp = await client.post(
        "/api/v1/alertmanager",
        json={
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "HighErrorRate", "severity": "critical"},
                    "annotations": {"summary": "错误率过高（已超 5%）"},
                }
            ],
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"received": 1}


@pytest.mark.asyncio
async def test_alertmanager_webhook_empty_payload(client: AsyncClient):
    """空告警列表也应正常响应。"""
    resp = await client.post("/api/v1/alertmanager", json={"alerts": []})

    assert resp.status_code == 200
    assert resp.json() == {"received": 0}
