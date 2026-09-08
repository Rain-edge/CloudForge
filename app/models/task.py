"""Task ORM 模型 — SQLAlchemy 2.0 声明式映射。

对应迁移：alembic/versions/025e00870d71_initial.py
对应 DTO：app/schemas/task.py
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""
    pass


class TaskStatus(str, enum.Enum):
    """任务状态。继承 str 便于 JSON 序列化。"""
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class Task(Base):
    """任务表。"""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4  # Python 侧生成主键
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )
    # server_default：由数据库填充，Python 不传值时也会自动生成
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
