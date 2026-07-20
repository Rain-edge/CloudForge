"""
Task CRUD API — 演示 RESTful 五件套。
=========================================
端点一览：
  GET    /tasks              → 列表（按创建时间倒序）
  POST   /tasks              → 创建（201 Created）
  GET    /tasks/{task_id}    → 详情（404 如果不存在）
  PATCH  /tasks/{task_id}    → 部分更新（仅更新提供的字段）
  DELETE /tasks/{task_id}    → 删除（204 No Content）

URL 前缀：/tasks（在 router 定义时指定 prefix）

HTTP 动词语义（REST 约定）：
  GET     — 幂等、安全（不修改资源）
  POST    — 非幂等（每次创建新资源）
  PATCH   — 部分更新（只传要改的字段）
  DELETE  — 幂等（删除已删除的资源仍返回 204）

数据库操作流程（以 create 为例）：
  1. FastAPI 解析请求体 → TaskCreate Pydantic 对象
  2. 路由函数创建 Task ORM 实例
  3. db.add(task) → 标记为 "待插入"
  4. await db.commit() → 发送 INSERT SQL
  5. await db.refresh(task) → 从数据库重新加载（获得 id / created_at 等）
  6. 返回 task → Pydantic 序列化为 TaskResponse JSON
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

# prefix="/tasks" → 所有路由路径自动加上 /tasks 前缀
router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── 列表：GET /tasks ──────────────────────────────────────
@router.get("", response_model=list[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    """获取所有任务列表，按创建时间倒序排列。"""
    result = await db.execute(select(Task).order_by(Task.created_at.desc()))
    return result.scalars().all()  # .scalars().all() 提取 ORM 实例列表


# ── 创建：POST /tasks ─────────────────────────────────────
@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    """创建新任务。

    Args:
        body: TaskCreate（Pydantic 自动校验 title 非空且 ≤255 字符）

    Returns:
        201 Created + TaskResponse JSON
    """
    task = Task(title=body.title)   # 创建 ORM 实例（id/status/时间戳由默认值填充）
    db.add(task)                    # 标记为待插入
    await db.commit()               # 执行 INSERT
    await db.refresh(task)          # 从数据库重新加载（获得 server_default 生成的值）
    return task                     # Pydantic 自动序列化为 TaskResponse


# ── 详情：GET /tasks/{task_id} ────────────────────────────
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """根据 UUID 获取单个任务。

    FastAPI 自动将路径参数从字符串转换为 uuid.UUID。
    如果格式不正确，自动返回 422 错误。
    """
    task = await db.get(Task, task_id)  # 主键查询（利用 SQLAlchemy identity map）
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── 更新：PATCH /tasks/{task_id} ──────────────────────────
@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    """部分更新任务（PATCH 语义：只更新请求中提供的字段）。

    model_dump(exclude_unset=True)：
      只包含用户实际传入的字段，未传入的字段不出现在字典中。
      举例：PATCH {"status":"done"} → update_data = {"status":"done"}
      不会把 title=None 也覆盖掉。

    setattr(task, key, value)：
      动态设置 ORM 对象属性，避免逐个判断字段。
    """
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 只提取用户实际传入的字段
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)  # 刷新以获取数据库更新后的时间戳等
    return task


# ── 删除：DELETE /tasks/{task_id} ─────────────────────────
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """删除任务。成功返回 204 No Content（无响应体）。

    幂等性说明：
      如果任务不存在，返回 404。这是应用层面的选择。
      严格 REST 风格下 DELETE 应是幂等的（已删除再次 DELETE 仍返回 204）。
    """
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
    # 显式返回 204 Response（不走 Pydantic 序列化）
    return Response(status_code=status.HTTP_204_NO_CONTENT)
