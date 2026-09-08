"""Task CRUD — RESTful 端点。

  GET    /tasks            列表（按 created_at 倒序）
  POST   /tasks            创建（201）
  GET    /tasks/{task_id}  详情（不存在 404）
  PATCH  /tasks/{task_id}  部分更新
  DELETE /tasks/{task_id}  删除（204）
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_tasks, cache_invalidate_tasks, cache_set_tasks
from app.core.database import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db)):
    """获取所有任务，按创建时间倒序；优先读 Redis 缓存（命中省一次 DB 查询）。"""
    # 读路径：缓存命中直接返回（dict 列表，response_model 会再校验一次）
    cached = await cache_get_tasks()
    if cached is not None:
        return cached

    result = await db.execute(select(Task).order_by(Task.created_at.desc()))
    tasks = result.scalars().all()

    # 回填缓存：ORM → JSON 兼容 dict（datetime 转 ISO 字符串）
    payload = [TaskResponse.model_validate(t).model_dump(mode="json") for t in tasks]
    await cache_set_tasks(payload)
    return tasks


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    """创建任务。commit 后 refresh 以读取 server_default 生成的字段。"""
    task = Task(title=body.title)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await cache_invalidate_tasks()  # 写操作后失效列表缓存
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """按主键查询；格式错误自动 422，不存在返回 404。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    """部分更新。exclude_unset=True 只取用户传入字段，避免覆盖为 None。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    await cache_invalidate_tasks()  # 写操作后失效列表缓存
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """删除任务。不存在返回 404（应用层选择，非严格 REST 幂等）。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
    await cache_invalidate_tasks()  # 写操作后失效列表缓存
    return Response(status_code=status.HTTP_204_NO_CONTENT)
