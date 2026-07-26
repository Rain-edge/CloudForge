"""ORM 模型包入口 — 导入所有模型以注册到 Base.metadata。

未导入的模型不会出现在 metadata 中，导致 create_all / alembic autogenerate 漏表。
新增模型时记得在此 import。
"""
from app.core.database import engine  # noqa: F401
from app.models.task import Base, Task  # noqa: F401
