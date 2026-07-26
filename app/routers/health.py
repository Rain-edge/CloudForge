"""健康检查 — GET /health，供 K8s liveness/readiness 探针使用。

返回 200 表示健康，503 表示数据库不可达（Service 不再路由流量到此 Pod）。
"""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import async_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """验证数据库连接；故障时返回 503 触发 K8s 摘流。"""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    if db_status == "error":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "db": "error"},
        )
    return {"status": "ok", "db": db_status}
