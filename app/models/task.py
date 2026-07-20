"""
ORM 模型 — Task（演示：一个简单的待办任务表）。
=====================================================
本文件演示了 SQLAlchemy 2.0 的声明式映射（Mapped + mapped_column）写法：

  - UUID 主键，Python 侧生成（uuid.uuid4()）
  - 枚举类型字段（TaskStatus：pending / in_progress / done）
  - 自动时间戳（created_at / updated_at）
  - server_default：由数据库填充默认值（时间戳）
  - 继承 Base，配合 alembic 自动生成迁移

对照关系：
  本文件   → alembic/versions/025e00870d71_initial.py 迁移
  本文件   → app/schemas/task.py Pydantic DTO（序列化/验证）
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ── ORM 基类 ──────────────────────────────────────────────
# 所有模型继承自此基类。SQLAlchemy 通过它自动发现表定义。
class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


# ── 任务状态枚举 ──────────────────────────────────────────
# 数据库层和 Python 层共享同一枚举定义。
class TaskStatus(str, enum.Enum):
    """任务状态枚举（str 子类便于 JSON 序列化）。"""
    pending = "pending"          # 待处理
    in_progress = "in_progress"  # 进行中
    done = "done"                # 已完成


# ── Task ORM 模型 ─────────────────────────────────────────
class Task(Base):
    """任务数据表模型。

    字段：
      id          — UUID 主键，Python 侧生成（uuid.uuid4()）
      title       — 任务标题，最大 255 字符（VARCHAR(255)）
      status      — 任务状态，默认 pending
      created_at  — 创建时间，数据库自动填充（NOW()）
      updated_at  — 更新时间，数据库自动填充（NOW()）
    """
    __tablename__ = "tasks"

    # primary_key=True + default=uuid.uuid4：主键由 Python 生成 UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # 标题不允许为空（nullable=False）
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # 枚举列：只接受 pending / in_progress / done 三种值
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )

    # server_default=func.now()：由数据库填充默认时间戳
    # 即使 Python 代码不传值，数据库也会自动填充
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
