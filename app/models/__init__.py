"""
models 包入口 — 导入所有 ORM 模型，确保 Base.metadata 包含完整的表信息。

为什么需要这个文件？
  - SQLAlchemy 的 DeclarativeBase 通过继承关系自动注册表定义
  - 但如果某个模型文件从未被 import，它的表就不会出现在 Base.metadata.tables 中
  - create_all() 和 alembic autogenerate 依赖 Base.metadata 知道所有表
  - 所以必须在包入口  import 所有模型文件

如果你新增了模型文件（如 app/models/user.py），记得在这里 import。
"""
# 导入引擎和 ORM 基类（触发 create_all / alembic 时使用）
from app.core.database import engine  # noqa: F401

# 导入所有模型 → 确保 Base.metadata 包含完整的表信息
from app.models.task import Base, Task  # noqa: F401
