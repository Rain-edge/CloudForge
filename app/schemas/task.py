"""Pydantic V2 Schema — API 请求/响应 DTO，与 ORM 模型职责分离。

分离的好处：API 契约不随表结构变化，且可对创建/更新应用不同校验规则。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    """创建任务请求 — POST /tasks。"""
    title: str = Field(..., min_length=1, max_length=255)  # 与 VARCHAR(255) 对齐


class TaskUpdate(BaseModel):
    """更新任务请求 — PATCH /tasks/{id}。所有字段可选，实现部分更新。"""
    title: str | None = Field(None, min_length=1, max_length=255)
    status: TaskStatus | None = None


class TaskResponse(BaseModel):
    """任务响应 — 从 ORM 对象直接序列化。"""

    model_config = ConfigDict(from_attributes=True)  # 允许从 ORM 属性读取

    id: uuid.UUID
    title: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
