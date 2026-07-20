"""
健康检查 API — 供 Kubernetes liveness/readiness probe 使用。
===============================================================
端点：GET /health

返回值说明：
  200 {"status":"ok","db":"connected"}     ← 全部正常
  503 {"status":"degraded","db":"error"}   ← 数据库不可达

Kubernetes 探针配置（Helm Chart 自动生成）：
  livenessProbe:  存活探针 — 如果持续失败，kubelet 重启 Pod
  readinessProbe: 就绪探针 — 如果失败，Service 不会将流量路由到此 Pod

探针设计要点：
  1. 必须轻量（简单 SELECT 1，避免重建连接池）
  2. 必须包含关键依赖检查（数据库）
  3. 失败时应返回非 200 状态码（K8s 只认 200-399 为成功）
"""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import async_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """健康检查：验证数据库连接可用性。

    Returns:
        200: {"status": "ok", "db": "connected"}
        503: {"status": "degraded", "db": "error"}
    """
    # 尝试执行 SELECT 1 验证数据库连接
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # 数据库故障时返回 503，让 K8s Service 不路由流量到此 Pod
    if db_status == "error":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "db": "error"},
        )
    return {"status": "ok", "db": db_status}
