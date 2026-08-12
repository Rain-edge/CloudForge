# 第二周任务答案

> 对应 `week2-plan.md` 中设计的每日任务、检验标准与自检问题的参考答案。
> 建议先自己尝试回答，再对照本文件查漏补缺。

---

## Day 1 答案 — Docker 镜像构建原理

### ✅ 检验：Dockerfile 每条指令的作用和执行顺序

`docker/Dockerfile` 逐指令拆解：

| 指令 | 作用 | 为什么需要 |
|------|------|-----------|
| `FROM python:3.11-slim` | 指定基础镜像 | slim(Debian+glibc) 有预编译 C 扩展 wheel，构建快 |
| `RUN sed -i ... aliyun` | 把 apt 源换成阿里云 | 国内访问 Debian 官方源慢 |
| `RUN pip config set ... aliyun` | 把 pip 源换成阿里云 | 国内访问 PyPI 慢 |
| `RUN apt-get install libpq-dev gcc` | 安装 PostgreSQL 客户端库 | asyncpg 是 libpq 的 Python 绑定，运行/编译都需要它 |
| `RUN groupadd/useradd cloudforge` | 创建非 root 系统用户 | 安全最佳实践：容器内不用 root 跑应用 |
| `WORKDIR /app` | 设置工作目录 | 后续 COPY/CMD 都基于此路径 |
| `COPY pyproject.toml ./` | 先复制依赖清单 | **层缓存关键**：依赖不常变，先复制它装依赖，改代码不会重装依赖 |
| `RUN pip install ...` | 安装全部 Python 依赖 | 一次装齐，避免逐层装 |
| `COPY app/ /app/app/` | 复制应用源码 | 最后复制源码，代码变动只重建这一层 |
| `ENV PYTHONPATH=/app` | 让 `app.main:app` 可导入 | Python 从 /app 找包 |
| `ENV PYTHONUNBUFFERED=1` | 日志不缓冲 | 否则容器日志要等缓冲区满才输出，排障困难 |
| `USER cloudforge` | 切换到非 root 用户 | 降低容器被攻破后的危害 |
| `EXPOSE 8000` | 声明容器监听端口 | 文档性声明（实际暴露靠 -p/ports） |
| `CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]` | 启动命令 | 用 python -m uvicorn 而非 uvicorn 命令，兼容性更好 |

**执行顺序**：FROM → RUN(换源) → RUN(装系统库) → RUN(建用户) → WORKDIR → COPY(pyproject) → RUN(pip install) → COPY(app) → ENV → USER → EXPOSE → CMD

**层缓存机制**：

```
Dockerfile 分层构建（每一行生成一层）
──────────────────────────────────────
FROM python:3.11-slim        ┐
RUN sed 换源                 │ 这 4 层几乎不变
RUN apt-get install libpq    │ → 永远命中缓存
RUN useradd                  ┘
WORKDIR /app                 → 不变
COPY pyproject.toml          → 只依赖清单变了才重建
RUN pip install              → 依赖列表不变 → 复用缓存层
COPY app/                    → 源码一变，只重建这一层
...
```

**收益**：开发时只改代码，`docker build` 从"COPY app"层才开始重跑，秒级完成。

---

## Day 2 答案 — Docker Compose 服务编排

### ✅ 检验 1：三个服务的启动时序图

```
docker compose up -d
  │
  ├─ 1. 创建网络 cloudforge_default（桥接网络）
  ├─ 2. 创建卷 pgdata（命名卷，PG 数据持久化）
  ├─ 3. 启动 postgres ──▶ pg_isready 每 3s 探测，5 次失败则 unhealthy
  │                        │
  │                        ├─ healthy ✅
  ├─ 4. 启动 redis ──────▶ redis-cli ping 每 3s 探测
  │                        │
  │                        ├─ healthy ✅
  ├─ 5. 两个依赖 healthy 后 → 启动 app
  │     app lifespan:
  │       ├─ SELECT 1 连接 PG（失败重试 10 次 × 2s，耗尽则启动失败）
  │       ├─ Base.metadata.create_all 自动建表
  │       └─ yield → 应用开始服务
  └─ 6. 路由就绪：/health、/tasks、/metrics、/docs
```

### ✅ 检验 2：为什么容器里 `postgres` 能代替 localhost

1. Compose 自动创建默认网络 `cloudforge_default`（bridge 类型）
2. 每个 service 加入该网络，**服务名被注册为内置 DNS 记录**
3. 容器内解析 `postgres` → 自动返回该容器在桥接网络中的内网 IP
4. 所以 app 容器内用 `postgres:5432` 就能连上，无需知道宿主 IP

> 对照：容器内写 `localhost` 反而是错的——localhost 指容器自己，app 容器里没有 PG。

---

## Day 3 答案 — 数据持久化与环境变量

### ✅ 检验：`docker compose down` vs `docker compose down -v`

| 命令 | 停止容器 | 删除容器 | 删除网络 | 删除命名卷(pgdata) | 数据 |
|------|:---:|:---:|:---:|:---:|------|
| `down` | ✅ | ✅ | ✅ | ❌ | **保留**（再 up 数据还在） |
| `down -v` | ✅ | ✅ | ✅ | ✅ | **永久删除** |

**记忆口诀**：`-v` = volume，删卷才丢数据。

### 环境变量完整链路

```
docker-compose.yml                         app/core/config.py                    app/core/database.py
─────────────────                         ───────────────────                    ─────────────────────
environment:                              class Settings(BaseSettings):          engine = create_async_engine(
  - CF_DATABASE_URL=...                      database_url: str =                   settings.database_url,
    postgresql+asyncpg://                    "postgresql+asyncpg://                 pool_pre_ping=True,
    cloudforge:cloudforge@                   cloudforge:cloudforge@                 pool_size=10,
    postgres:5432/cloudforge                 localhost:5432/cloudforge"             max_overflow=20 ...
       │                                         │                                     │
       └── 容器环境变量 ──▶ env_prefix="CF_" 自动映射 ──▶ settings 单例 ──▶ asyncpg 连接 PG
```

**关键机制（pydantic-settings）**：
- 配置优先级：代码默认值 < `.env` 文件 < 系统环境变量（最高）
- `env_prefix="CF_"`：`database_url` 字段自动对应 `CF_DATABASE_URL` 环境变量
- Compose 里覆盖了默认值：默认是 `localhost`，Compose 里改成 `postgres`（服务名）

---

## Day 4 答案 — 连接池与生产级数据库配置

### ✅ 检验：连接池 5 个核心参数各自解决的问题

| 参数 | 值 | 解决的问题 | 类比 |
|------|-----|-----------|------|
| `pool_size=10` | 10 | 常驻 10 个连接复用，避免每请求新建 TCP 连接 | 银行柜台 10 个固定窗口 |
| `max_overflow=20` | 20 | 高峰期临时再开 20 个（峰值 30），低峰回收 | 忙时临时加开窗口 |
| `pool_pre_ping=True` | True | 检出连接前先 `SELECT 1`，发现死连接就丢弃重建 | 用前先确认电话线没断 |
| `pool_recycle=3600` | 3600s | 连接活过 1 小时强制回收重建，防止中间设备静默断连 | 电话打久了强制重拨 |
| `command_timeout=30` | 30s | 单条 SQL 超 30s 就报错，防止慢查询拖死连接池 | 窗口排队超时就提示 |

**为什么需要 pool_pre_ping**：PostgreSQL 重启、空闲超时、防火墙/NAT 都可能把服务端连接悄悄关掉，但客户端不知道，拿到的连接是"僵尸连接"。`pool_pre_ping=True` 在每次取出连接时执行轻量 `SELECT 1`，发现失效立即替换为新连接。

### 并发实验预期结果

50 个并发请求打 `/health`，`pg_stat_activity` 中连接数不会到 50 —— 最多 30（pool_size 10 + max_overflow 20），其余请求**排队等待**池中连接释放。这就是连接池的"限流"效果，防止打爆 PG 的 `max_connections`。

---

## Day 5 答案 — Dockerfile 优化与多架构构建

### ✅ 检验：slim vs alpine 怎么选

| 维度 | alpine | slim (Debian) |
|------|--------|---------------|
| 镜像大小 | ~50MB | ~150-300MB |
| libc | musl | glibc |
| C 扩展（asyncpg/bcrypt） | 无预编译 wheel，需 gcc 现场编译 | 有预编译 wheel，秒装 |
| 构建时间（本项目） | 5-10 分钟 | ~30 秒 |
| 兼容性 | 偶有兼容坑（如某些 wheel 不支持 musl） | 官方支持最好 |

**本项目为什么选 slim**：asyncpg（PG 驱动）需要编译，alpine 下太慢；slim 直接装二进制 wheel，构建速度快、稳定。这也是 README 中"多阶段构建 <100MB"的优化方向——如果追求极致体积，会用 alpine + 多阶段。

### CI 多架构构建的意义

```
build-push job（matrix: amd64 + arm64）
  ├─ linux/amd64 镜像 → 推 Docker Hub：cloudforge:abc1234-amd64
  └─ linux/arm64 镜像 → 推 Docker Hub：cloudforge:abc1234-arm64
        ↓
create-manifest job（合并）
  └─ cloudforge:abc1234（multi-arch manifest）
        ↓
用户 docker pull cloudforge:abc1234 → Docker 自动按本机架构拉对应镜像
```

- **amd64**：传统 x86 服务器（阿里云/腾讯云 ECS、AWS EC2）
- **arm64**：Mac M1/M2、ARM 云服务器（AWS Graviton）、树莓派
- 没有 manifest 的话，ARM 机器拉 x86 镜像会直接报 "exec format error"

---

## 周末口述自检答案

### ① 为什么要容器化？

1. **环境一致性**：同一镜像跑在开发/测试/生产，杜绝"在我机器上能跑"
2. **依赖隔离**：每个服务打包自己的运行时（Python 版本、系统库），互不干扰
3. **轻量快速**：秒级启动、资源占用远小于虚拟机
4. **可移植性**：一次构建，本地/云/边缘随处运行
5. **标准化交付**：镜像即交付物，配合 CI/CD 全自动
6. **编排基础**：Docker Compose/K8s 都建立在容器之上

### ② depends_on vs healthcheck 的区别？

| | depends_on | healthcheck |
|--|-----------|-------------|
| 角色 | **声明依赖关系**（谁先谁后） | **定义就绪标准**（怎么算健康） |
| 默认行为 | 只等容器"启动"（status=running） | 无（不配就没有判断标准） |
| 组合 | `depends_on + condition: service_healthy` = 等依赖**真正就绪** | `pg_isready` 探测通过才算 healthy |

**为什么只靠 depends_on 不够**：容器启动 ≠ 服务就绪。PG 容器起来了但还在 crash recovery，此时 app 连上去就失败 → 崩溃 → restart 死循环。healthcheck 给了"就绪"一个可量化的标准。

### ③ 连接池解决什么问题？

- **性能**：TCP 握手 + 认证开销大（毫秒级），每请求新建连接浪费；池化复用省掉
- **资源保护**：限制最大连接数（10+20），防止高并发打爆 PG 的 max_connections
- **稳定性**：stale 连接检测（pre_ping）、定时回收（recycle）、超时控制，避免"跨调用进程丢失"类故障

### ④ 命名卷 vs bind mount？

| 维度 | 命名卷（pgdata） | bind mount（./app:/app/app） |
|------|-----------------|------------------------------|
| 存储位置 | Docker 管理（/var/lib/docker/volumes/...） | 宿主机指定路径 |
| 用途 | **持久化数据**（数据库） | **开发热重载**（改代码立即生效） |
| 生命周期 | `down` 不删，`down -v` 才删 | 随目录存在，不随容器 |
| 跨平台 | 一致 | 路径/权限问题多（Windows、SELinux） |
| 性能 | 好（Docker 原生管理） | 依赖宿主文件系统 |

**项目用法**：PG 数据 → 命名卷（要持久化）；app 代码 → bind mount（要热重载）。

### ⑤ slim vs alpine 怎么选？

- **有 C 扩展依赖（asyncpg/bcrypt 等）** → 优先 slim：有预编译 wheel，构建快、稳定
- **纯 Python / 无 C 扩展** → 可以 alpine：镜像小一半，无编译问题
- **追求极致体积** → alpine + 多阶段构建：builder 编译 + runtime 只拷产物
- **本项目**：选了 slim，把"能跑、跑得快"放在"体积小"前面

---

## 整周检验清单答案

### 完整闭环命令

```bash
# 1. 构建（--no-cache 强制全量重跑，验证完整构建流程）
docker compose build --no-cache app

# 2. 启动
docker compose up -d
docker compose ps            # 看 3 个服务都是 healthy

# 3. 验证 API
curl http://localhost:8000/health
# → {"status":"ok","db":"connected"}

# 4. CRUD 全流程
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"learn docker"}'
# → 201 + task JSON（含 id/created_at）

curl http://localhost:8000/tasks
curl -X PATCH http://localhost:8000/tasks/<id> \
  -H "Content-Type: application/json" -d '{"status":"done"}'
curl -X DELETE http://localhost:8000/tasks/<id>   # → 204

# 5. 看日志
docker compose logs -f app

# 6. 清理
docker compose down -v
```

### 核心概念一句话版

| 问题 | 一句话答案 |
|------|-----------|
| `postgres` 为什么能代替 localhost | Compose 内置 DNS 把服务名解析为容器内网 IP |
| healthcheck 的作用 | 定义"服务就绪"标准，配合 depends_on 避免 app 连未就绪的依赖 |
| 连接池 5 参数 | size/overflow 控资源，pre_ping 防死连接，recycle 防静默断连，timeout 防卡死 |
| 环境变量链路 | Compose `CF_` 变量 → pydantic-settings 自动映射 → settings 单例 → SQLAlchemy Engine |
| down vs down -v | -v 才删命名卷，才真正丢数据 |
| slim vs alpine | 有 C 扩展选 slim（预编译 wheel），追求小体积且无 C 扩展才选 alpine |
