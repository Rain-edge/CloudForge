# 第二周实施计划：容器化 + Docker Compose

> **目标**：理解为什么要容器化，以及多服务之间如何通信。
> **预计总时长**：约 7 小时（工作日每天 1 小时 + 周末 2 小时）

---

## Day 1（周一）— Docker 镜像构建原理

**目标**：理解 Dockerfile 每一行在做什么，能独立构建镜像。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `docker/Dockerfile`** | 逐行读，对照注释理解 `FROM`、`RUN`、`COPY`、`USER`、`CMD` 每条指令的作用 | 20min |
| 2 | **理解层缓存机制** | 画出 Docker 构建的层图：为什么先 COPY pyproject.toml 再 COPY app/？修改 `app/main.py` 后重新 build，观察哪几层用了 cache | 15min |
| 3 | **手动构建 + 运行** | `docker build -t cloudforge:dev -f docker/Dockerfile .` 然后 `docker images` 看镜像大小，再 `docker run -d -p 8000:8000 cloudforge:dev` 启动单容器 | 15min |
| 4 | **进入容器内部探索** | `docker exec -it <容器名> bash`，看看文件系统、`whoami`（确认是 cloudforge 用户）、`ls /app` | 10min |

**✅ 检验**：不看 Dockerfile，能说出每条指令的作用和执行顺序。

**核心知识点**：

| 概念 | 在项目中的体现 | 说明 |
|------|---------------|------|
| 基础镜像选型 | `FROM python:3.11-slim` | slim(Debian) 有预编译 C 扩展 wheel，构建 30s vs alpine 的 5-10 分钟 |
| 层缓存优化 | 先 `COPY pyproject.toml` → `pip install` → 再 `COPY app/` | 依赖不常变，源码常变；修改代码不会触发重新安装依赖 |
| 非 root 运行 | `groupadd -r cloudforge && useradd -r` + `USER cloudforge` | 安全最佳实践，即使容器被攻破也只拿到普通用户权限 |
| 国内镜像加速 | `sed` 换阿里云源 | 解决 `apt-get`/`pip` 下载慢的问题 |
| 运行时依赖 | `apt-get install libpq-dev` | asyncpg 是 PG 客户端库的 Python 绑定，需要系统库 |

---

## Day 2（周二）— Docker Compose 服务编排

**目标**：理解三个服务如何协作，depends_on + healthcheck 的启动顺序。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `docker-compose.yml`** | 重点：3 个 service 的定义、`depends_on` + `condition: service_healthy`、`volumes`、`environment` | 15min |
| 2 | **启动 + 观察启动顺序** | `docker compose up -d`，然后 `docker compose logs -f` 观察 postgres 先变 healthy → redis 变 healthy → app 再启动 | 20min |
| 3 | **实验：破坏健康检查** | 故意改错 `CF_DATABASE_URL` 的密码 → `docker compose up -d` → 看 app 的 lifespan 重试 10 次后报错 | 15min |
| 4 | **理解 Docker 网络** | `docker compose exec app sh -c "nslookup postgres"` 验证 DNS 解析，`docker network ls` 查看自动创建的网络 | 10min |

**✅ 检验**：能画出三个服务的启动时序图，能解释 `postgres` 为什么能当主机名用。

**核心知识点**：

| 概念 | 在项目中的体现 | 说明 |
|------|---------------|------|
| depends_on + healthcheck | `condition: service_healthy` | Docker 原生 depends_on 只等容器启动；加 condition 才等**服务就绪** |
| healthcheck | `pg_isready`（PG）/ `redis-cli ping`（Redis） | 每 3s 检测一次，最多 15s，通过后才标记 healthy |
| Docker 网络 DNS | environment 中用 `postgres`、`redis` 做主机名 | Compose 自动创建桥接网络，服务名即 DNS 名 |
| 热重载 | `volumes: - ./app:/app/app` | 修改本地代码 → 容器内立即生效 |
| 重启策略 | `restart: unless-stopped` | 崩溃/Docker 重启后自动恢复；仅 `docker compose stop` 不重启 |

**服务启动全流程**：

```
docker compose up -d
  │
  ├─ 1. 创建网络 cloudforge_default
  ├─ 2. 启动 postgres → pg_isready 每 3s 检测 → (healthy)
  ├─ 3. 启动 redis    → redis-cli ping → (healthy)
  ├─ 4. 两个依赖都 healthy 后 → 启动 app
  ├─ 5. app lifespan 中再次 SELECT 1 确认 PG（最多重试 10 次）
  └─ 6. 自动建表 (create_all) → 开始接收请求
```

---

## Day 3（周三）— 数据持久化与环境变量

**目标**：理解卷（volume）的作用和 pydantic-settings 环境变量映射。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **验证数据持久化** | `docker compose exec postgres psql -U cloudforge -c "INSERT INTO tasks (title) VALUES ('test');"` → `docker compose down`（不加 -v） → 再 `up -d` → 查表数据还在 | 15min |
| 2 | **验证 -v 清理** | `docker compose down -v` → 再 `up -d` → 数据消失（pgdata 卷被删了） | 15min |
| 3 | **跟踪环境变量链路** | 从 `docker-compose.yml` 的 `CF_DATABASE_URL` → `app/core/config.py` 的 `Settings.database_url` → `app/core/database.py` 的 `create_async_engine` → 最终连到 PG，画完整配置流向图 | 15min |
| 4 | **热重载验证** | 修改 `app/routers/health.py` 里返回的 message → `docker compose restart app` → 确认改动生效 | 15min |

**✅ 检验**：能说清楚 `docker compose down` 和 `docker compose down -v` 的区别。

**环境变量流向图**：

```
docker-compose.yml                    app/core/config.py              app/core/database.py
─────────────────                    ───────────────────             ─────────────────────
environment:                         class Settings:                 create_async_engine(
  CF_DATABASE_URL=                    database_url: str =              settings.database_url,
    "postgresql+asyncpg://              "postgresql+asyncpg://          pool_pre_ping=True,
     cloudforge:cloudforge@              cloudforge:cloudforge@         pool_size=10,
     postgres:5432/cloudforge"            localhost:5432/cloudforge"     ...)
         │                                      │                            │
         └──── CF_ 前缀自动映射 ────────────────┘                            │
                                              └──────── 注入 ───────────────┘
```

---

## Day 4（周四）— 连接池与生产级数据库配置

**目标**：深入理解 `database.py` 中的连接池参数解决了什么问题。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `app/core/database.py`** | 逐行理解每个参数：`pool_size`、`max_overflow`、`pool_pre_ping`、`pool_recycle`、`connect_args` | 20min |
| 2 | **连接池实验** | 用 `for i in {1..50}; do curl -s http://localhost:8000/health &; done` 并发请求，观察 PG 连接数 `docker compose exec postgres psql -U cloudforge -c "SELECT count(*) FROM pg_stat_activity;"` | 15min |
| 3 | **模拟 stale 连接** | 思考：PG 重启后连接池里的旧连接会怎样 → `pool_pre_ping=True` 在检出前 SELECT 1 验证 → 死连接会被自动丢弃并新建 | 15min |
| 4 | **读 `.dockerignore`** | 理解为什么要排除 `__pycache__`、`.git`、`.pytest_cache` — 减小构建上下文，加速 `docker build` | 10min |

**✅ 检验**：能解释 `pool_pre_ping=True` 和 `pool_recycle=3600` 分别解决什么问题。

**连接池参数速查**：

| 参数 | 值 | 解决的问题 |
|------|-----|-----------|
| `pool_size` | 10 | 常驻连接数，复用减少 TCP 握手开销 |
| `max_overflow` | 20 | 高峰期额外连接数（峰值 30=10+20） |
| `pool_pre_ping` | True | 检出前验证连接有效性，防止使用已被 PG 关闭的 stale 连接 |
| `pool_recycle` | 3600 | 1 小时后强制回收，防止防火墙/NAT/负载均衡器静默断开空闲连接 |
| `connect_args.timeout` | 10s | 建立连接超时，防止网络抖动时卡死 |
| `connect_args.command_timeout` | 30s | 单条 SQL 执行超时，防止慢查询耗尽连接 |

---

## Day 5（周五）— Dockerfile 优化与多架构构建

**目标**：理解镜像优化的方向和多架构支持的意义。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **对比 alpine vs slim** | 回顾 RUNBOOK 里踩过的坑：alpine 用 musl libc 需要编译 C 扩展极慢；slim 用 glibc + 预编译 wheel 秒装 | 15min |
| 2 | **理解 CI 中的多架构构建** | 读 `.github/workflows/ci.yml` 的 `build-push` job，`linux/amd64`（x86 服务器）vs `linux/arm64`（Mac M1/M2、ARM 云服务器） | 15min |
| 3 | **理解 multi-arch manifest** | `create-manifest` job 把两个架构镜像合并：`docker pull cloudforge:latest` 自动拉适配架构 | 10min |
| 4 | **综合实践：从头跑一遍** | `docker compose down -v` → `docker compose build --no-cache app` → `docker compose up -d` → curl 所有端点 → 独立走完全流程 | 20min |

**✅ 检验**：不看文档，能独立完成 `build` → `up` → 验证 → `down -v` 的完整闭环。

---

## Day 6-7（周末）— 复盘与检验

**目标**：不看代码和文档，能独立完成所有操作并口头解释核心概念。

| 任务 | 具体操作 | 时长 |
|------|----------|------|
| **画架构图** | 不看代码画出：三个容器在 Docker 网络中的拓扑关系、PG 连接池的工作模型、环境变量从 Compose → Config → Engine 的流向 | 30min |
| **口述自检** | 回答以下问题：① 为什么要容器化？② depends_on vs healthcheck 的区别？③ 连接池解决什么问题？④ 命名卷 vs bind mount？⑤ slim vs alpine 怎么选？ | 15min |
| **独立跑一遍** | 从零开始：`docker compose build --no-cache` → `up -d` → curl CRUD 所有端点 → 健康检查 → 读日志 → `down -v` | 45min |
| **对照 week2-notes.md** | 读项目已有的周笔记作为参考答案，对比自己的理解 | 15min |
| **记录自己的笔记** | 把这一周学到的最重要的 5 个点写下来，用自己的话表述 | 15min |

---

## 常见坑点（来自 RUNBOOK.md 踩坑记录）

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `POSTGRES_PASSWORD` 被 YAML 解析为数组 | YAML 裸字符串被误解析 | 加引号：`"cloudforge"` |
| Dockerfile Alpine 版构建极慢 | musl libc 下 asyncpg/bcrypt 需编译 C 扩展 | 改用 `python:3.11-slim` |
| Docker Desktop 代理没开时反而报错 | 设置了代理地址但代理程序没启动 | 清空 Docker Desktop 的代理设置 |
| pip/apt 下载慢 | 官方源在国内慢 | Dockerfile 已配阿里云镜像源 |

---

## 检验标准（整周结束后应能回答）

- [ ] 能独立完成 `docker compose build` → `up` → 验证 → `down -v` 的完整闭环
- [ ] 能解释容器里 `postgres` 这个名字为什么能代替 localhost
- [ ] 能说出 healthcheck 在 depends_on 中起什么作用
- [ ] 能解释连接池 5 个核心参数各自解决的问题
- [ ] 能画出环境变量从 Compose → pydantic-settings → SQLAlchemy Engine 的完整链路
- [ ] 能说清楚 `docker compose down` 和 `docker compose down -v` 的区别
- [ ] 能对比 slim 和 alpine 的适用场景
