"""Task CRUD 集成测试 — 覆盖 5 个端点 + 404/422 错误路径。"""
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    """创建任务返回 201 与完整字段。"""
    resp = await client.post("/tasks", json={"title": "Learn FastAPI"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Learn FastAPI"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient):
    """列表按创建时间倒序返回。"""
    import asyncio

    await client.post("/tasks", json={"title": "Task A"})
    await asyncio.sleep(1.1)  # SQLite 时间戳秒级精度，需间隔确保 created_at 不同
    await client.post("/tasks", json={"title": "Task B"})

    resp = await client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "Task B"
    assert data[1]["title"] == "Task A"


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient):
    """按 ID 获取任务。"""
    create_resp = await client.post("/tasks", json={"title": "Read docs"})
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Read docs"


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient):
    """PATCH 只修改传入字段。"""
    create_resp = await client.post("/tasks", json={"title": "Old title"})
    task_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Old title"
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    """删除返回 204，再次获取返回 404。"""
    create_resp = await client.post("/tasks", json={"title": "To delete"})
    task_id = create_resp.json()["id"]

    resp = await client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 204
    assert resp.text == ""

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_task_404(client: AsyncClient):
    """访问不存在的任务返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/tasks/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task_404(client: AsyncClient):
    """更新不存在的任务返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/tasks/{fake_id}", json={"status": "done"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_404(client: AsyncClient):
    """删除不存在的任务返回 404。"""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/tasks/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_payload(client: AsyncClient):
    """空 title 触发 Pydantic 校验，返回 422。"""
    resp = await client.post("/tasks", json={"title": ""})
    assert resp.status_code == 422
    error_detail = resp.json()["detail"][0]
    assert error_detail["loc"] == ["body", "title"]
    assert error_detail["type"] == "string_too_short"
