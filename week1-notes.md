# CloudForge 项目：架构学习笔记模板

## 第一周：FastAPI 核心架构

### 第 1 天：入口 + 配置

- **文件**: app/main.py + app/core/config.py
- **核心问题**:
  - 一个 HTTP 请求进入 FastAPI 后依次经过哪些组件？
  - lifespan 的作用是什么？yield 前后的代码分别在什么时候执行？
  - pydantic-settings 如何实现环境的自动切换？
- **动手**: 修改 .env 文件中的 CF_DATABASE_URL，观察应用启动行为变化。

### 第 2 天：数据库引擎

- **文件**: app/core/database.py
- **核心问题**:
  - pool_size, max_overflow, pool_recycle 各自解决什么问题？
  - async/await 相比同步代码的优势是什么？
  - Depends(get_db) 的执行时机是什么？
- **动手**: 在 get_db 中加入打印语句，观察每个请求产生一个 session。

### 第 3 天：ORM 模型 + Schema

- **文件**: app/models/task.py + app/schemas/task.py
- **核心问题**:
  - ORM 模型和 Pydantic Schema 各负责什么？为什么不合并？
  - UUID 主键相比自增整数的优缺点？
  - Pydantic V2 的 from_attributes 替代了 V1 的什么？
- **动手**: 给 Task 模型加一个 `priority` 字段，同步修改 Schema，运行测试检查。

### 第 4 天：RESTful API

- **文件**: app/routers/tasks.py
- **核心问题**:
  - 为什么创建流程是 add → commit → refresh 而不是只做 add？
  - PATCH 中的 exclude_unset=True 解决了什么问题？
  - GET/POST/PATCH/DELETE 哪些是幂等的？
- **动手**: 给 tasks router 加一个 `GET /tasks?status=pending` 过滤端点。

### 第 5 天：健康检查 + 可观测性入口

- **文件**: app/routers/health.py + app/core/metrics.py + app/core/telemetry.py + app/middleware/logging.py
- **核心问题**:
  - K8s 的 livenessProbe 和 readinessProbe 有什么区别？
  - Prometheus 的 Counter 和 Histogram 各适合什么数据类型？
  - OpenTelemetry 的 Trace 链是怎么建立起来的？
- **动手**: 在 Grafana 中手动查询 http_requests_total 并画出 QPS 曲线。

### 第 6 天：Review + 测试

- **文件**: app/tests/test_tasks.py + app/tests/conftest.py
- **核心问题**:
  - 为什么测试用 SQLite 而不是真实 PostgreSQL？
  - conftest.py 中的 dependency_overrides 在做什么？
- **动手**: 新增一个测试用例，验证创建时 title 为空返回 422。

### 第 7 天：独立重跑

不看笔记本，独立完成：
1. curl 调通健康检查 → 列出任务 → 创建任务 → 更新任务 → 删除任务
2. 解释 main.py 中 6 个步骤的作用
3. 画出一张请求的完整生命周期图
