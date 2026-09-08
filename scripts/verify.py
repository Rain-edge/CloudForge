"""CloudForge E2E 验证脚本 — 测试不依赖 DB 的端点。"""
import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


async def verify():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        results = []

        # /health：200=健康，503=DB 不可达，均合法
        r = await c.get("/health")
        data = r.json()
        ok = r.status_code in (200, 503) and data["status"] in ("ok", "degraded")
        results.append(("GET /health", ok, str(data)))

        # /health/live：不依赖 DB，必须 200（liveness 探针）
        r = await c.get("/health/live")
        ok = r.status_code == 200 and r.json().get("status") == "alive"
        results.append(("GET /health/live", ok, str(r.json())))

        # /metrics
        r = await c.get("/metrics")
        lines = r.text.strip().split("\n")
        metric_lines = [l for l in lines if l and not l.startswith("#")]
        ok = r.status_code == 200 and len(metric_lines) > 0
        results.append(("GET /metrics", ok, f"{len(metric_lines)} metric lines"))

        # /docs
        r = await c.get("/docs")
        ok = r.status_code == 200
        results.append(("GET /docs", ok, str(r.status_code)))

        # /openapi.json
        r = await c.get("/openapi.json")
        oapi = r.json()
        paths = list(oapi["paths"].keys())
        ok = r.status_code == 200 and "/tasks" in str(paths)
        results.append(("GET /openapi.json", ok, str(paths)))

        # 路由清单校验
        all_routes = set()
        for route in app.routes:
            if hasattr(route, "methods"):
                for m in route.methods:
                    all_routes.add(f"{m} {route.path}")
        required = ["GET /health", "GET /metrics", "GET /tasks", "POST /tasks",
                     "GET /tasks/{task_id}", "PATCH /tasks/{task_id}",
                     "DELETE /tasks/{task_id}",
                     "GET /docs", "GET /openapi.json"]
        missing = [r for r in required if not any(r in a for a in all_routes)]
        ok = len(missing) == 0
        results.append(("Required routes", ok, f"missing={missing}" if missing else "all present"))

        # 输出结果
        print("=" * 60)
        print("  CloudForge E2E Verification")
        print("=" * 60)
        all_pass = True
        for name, ok, detail in results:
            status = "PASS" if ok else "FAIL"
            if not ok:
                all_pass = False
            print(f"  [{status}] {name}: {detail}")
        print("=" * 60)
        if all_pass:
            print("  ALL CHECKS PASSED")
        else:
            print("  SOME CHECKS FAILED - review above")
        print()

        # /tasks CRUD 依赖 PostgreSQL，需 docker compose up
        print("  Note: /tasks CRUD requires PostgreSQL (docker compose up).")
        print("  Tests pass with in-memory SQLite (pytest).")
        print()


if __name__ == "__main__":
    asyncio.run(verify())
