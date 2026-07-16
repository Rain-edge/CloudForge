import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient):
    resp = await client.post("/tasks", json={"title": "Learn K8s"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Learn K8s"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient):
    # empty initially
    resp = await client.get("/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # add one
    await client.post("/tasks", json={"title": "Write Dockerfile"})
    resp = await client.get("/tasks")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient):
    create_resp = await client.post("/tasks", json={"title": "Get me"})
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get me"


@pytest.mark.asyncio
async def test_get_task_404(client: AsyncClient):
    resp = await client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient):
    create_resp = await client.post("/tasks", json={"title": "Old title"})
    task_id = create_resp.json()["id"]

    resp = await client.patch(f"/tasks/{task_id}", json={"title": "New title", "status": "done"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_update_task_404(client: AsyncClient):
    resp = await client.patch(
        "/tasks/00000000-0000-0000-0000-000000000000",
        json={"title": "Ghost"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    create_resp = await client.post("/tasks", json={"title": "To be deleted"})
    task_id = create_resp.json()["id"]

    resp = await client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_404(client: AsyncClient):
    resp = await client.delete("/tasks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_payload(client: AsyncClient):
    resp = await client.post("/tasks", json={})
    assert resp.status_code == 422
