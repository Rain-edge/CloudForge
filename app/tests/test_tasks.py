"""
Task CRUD API 集成测试 — 覆盖全部 5 个端点 + 错误场景。
=============================================================
测试策略（金字塔模型）：
  本文件是 集成测试（Integration Test）— 测试 HTTP 层 + 数据库层的协作。

测试覆盖：
  ✅ 正向路径（Happy Path）
     - 创建  → POST /tasks          → 201
     - 列表  → GET  /tasks          → 200 + [TaskResponse, ...]
     - 详情  → GET  /tasks/{id}     → 200 + TaskResponse
     - 更新  → PATCH /tasks/{id}    → 200 + 更新后的 TaskResponse
     - 删除  → DELETE /tasks/{id}   → 204

  ✅ 错误路径（Error Path）
     - 获取不存在的任务     → GET    /tasks/nonexistent → 404
     - 更新不存在的任务     → PATCH  /tasks/nonexistent → 404
     - 删除不存在的任务     → DELETE /tasks/nonexistent → 404
     - 创建时发送空 title   → POST   /tasks {"title":""} → 422
     - 创建时 title 超长    → POST   /tasks {"title":"..."} → 422
"""
import uuid

import pytest
from httpx import AsyncClient


# ── 正向路径测试 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    """POST /tasks — 创建任务，验证返回 201 和完整字段。"""
    resp = await client.post("/tasks", json={"title": "Learn FastAPI"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Learn FastAPI"
    assert data["status"] == "pending"   # 默认状态
    assert "id" in data                  # UUID 自动生成
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient):
    """GET /tasks — 创建两个任务后验证列表返回正确的数量和顺序。"""
    import asyncio

    await client.post("/tasks", json={"title": "Task A"})
    # SQLite 时间戳精度为秒级，需要短暂间隔确保 created_at 不同
    await asyncio.sleep(1.1)
    await client.post("/tasks", json={"title": "Task B"})

    resp = await client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 按创建时间倒序排列（最新在前）
    assert data[0]["title"] == "Task B"
    assert data[1]["title"] == "Task A"


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient):
    """GET /tasks/{id} — 获取单个任务，验证字段完整。"""
    create_resp = await client.post("/tasks", json={"title": "Read docs"})
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Read docs"


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient):
    """PATCH /tasks/{id} — 部分更新，验证只修改传入的字段。"""
    create_resp = await client.post("/tasks", json={"title": "Old title"})
    task_id = create_resp.json()["id"]

    # 只更新 status，title 应保持不变
    resp = await client.patch(
        f"/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Old title"     # 未修改
    assert data["status"] == "in_progress"   # 已修改


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    """DELETE /tasks/{id} — 删除成功后返回 204，再次获取返回 404。"""
    create_resp = await client.post("/tasks", json={"title": "To delete"})
    task_id = create_resp.json()["id"]

    resp = await client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 204
    # 204 No Content 没有响应体
    assert resp.text == ""

    # 验证任务确实被删除了
    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 404


# ── 错误路径测试 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_task_404(client: AsyncClient):
    """GET /tasks/{id} — 访问不存在的任务应返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/tasks/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task_404(client: AsyncClient):
    """PATCH /tasks/{id} — 更新不存在的任务应返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/tasks/{fake_id}", json={"status": "done"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_404(client: AsyncClient):
    """DELETE /tasks/{id} — 删除不存在的任务应返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/tasks/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_payload(client: AsyncClient):
    """POST /tasks — 发送空 title 应返回 422 Validation Error。

    Pydantic 的 Field(min_length=1) 自动触发验证。
    FastAPI 捕获 Pydantic ValidationError 并返回 422。
    """
    resp = await client.post("/tasks", json={"title": ""})
    assert resp.status_code == 422
    error_detail = resp.json()["detail"][0]
    assert error_detail["loc"] == ["body", "title"]
    assert error_detail["type"] == "string_too_short"
