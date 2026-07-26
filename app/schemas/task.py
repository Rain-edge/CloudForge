"""
Pydantic V2 数据模型（Schema / DTO） — API 请求与响应的类型定义。
====================================================================
本文件定义了 REST API 使用的三种 Pydantic 模型，与 ORM 模型职责分离：

  ┌─────────────────┬──────────────────────────────────────────────────┐
  │ 模型             │ 职责                                             │
  ├─────────────────┼──────────────────────────────────────────────────┤
  │ TaskCreate       │ POST /tasks 请求体验证（只接受 title）             │
  │ TaskUpdate       │ PATCH /tasks/{id} 请求体验证（所有字段可选）        │
  │ TaskResponse     │ 序列化 ORM 对象为 JSON 响应（from_attributes=True）│
  └─────────────────┴──────────────────────────────────────────────────┘

分离 ORM 模型和 Pydantic Schema 的好处：
  1. API 契约（Schema）不随数据库表结构变化而变化
  2. 可以有不同的验证规则（创建时 title 必填，更新时可选）
  3. 不会意外暴露数据库内部字段（如 ORM 反向关联）
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


# ── 请求模型 ──────────────────────────────────────────────
class TaskCreate(BaseModel):
    """创建任务请求 — POST /tasks。

    title 字段：
      - min_length=1：不允许空字符串
      - max_length=255：与数据库 VARCHAR(255) 保持一致
      - ...（Ellipsis）：必填字段，缺省时 Pydantic 返回 422 错误
    """
    title: str = Field(..., min_length=1, max_length=255)


class TaskUpdate(BaseModel):
    """更新任务请求 — PATCH /tasks/{task_id}。

    所有字段可选：仅更新请求中提供的字段（partial update / PATCH 语义）。
    title 和 status 均为 Optional，至少提供一个即可。
    """
    title: str | None = Field(None, min_length=1, max_length=255)
    status: TaskStatus | None = None


# ── 响应模型 ──────────────────────────────────────────────
class TaskResponse(BaseModel):
    """任务响应 — 从 ORM 对象直接序列化。

    ConfigDict(from_attributes=True)：
      允许 Pydantic 从 SQLAlchemy ORM 对象（Task 实例）的 . 属性读取字段值，
      替代旧的 class Config 中 orm_mode=True 写法。

    这是 Pydantic V2 的关键特性：
      以前写法：class Config: orm_mode = True
      现在写法：model_config = ConfigDict(from_attributes=True)
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
