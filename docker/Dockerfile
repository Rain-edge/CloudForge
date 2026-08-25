# CloudForge 应用镜像 — 基础版（python:3.11-slim，单阶段构建）
#
# 选型说明（为什么用 slim 而不是 alpine）：
#   - slim 基于 Debian，Python C 扩展（asyncpg、bcrypt、cryptography）有预编译 wheel
#   - 直接 pip install 二进制，不需要 gcc/musl-dev/postgresql-dev 等编译工具链
#   - 构建时间 30s 左右；alpine 下 asyncpg 从源码编译需 5-10 分钟
#   - 体积约 300MB，对生产可接受；追求极致小体积可切到多阶段 + alpine
FROM python:3.11-slim

# apt 源切到阿里云镜像（国内机器避免被 deb.debian.org 卡住；外网机器即使访问阿里云也能降级自动直连 debian）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# pip 也切到阿里云镜像，加速国内下载
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装运行时依赖：
#   libpq-dev — asyncpg / psycopg 需要 PostgreSQL 客户端动态库 libpq.so
#   gcc       — 少数没有 prebuilt wheel 的包（如果有）需要编译
# 最后删掉 apt 缓存，减小镜像层大小
RUN apt-get update -qq && apt-get install -y -qq libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（容器安全基线：默认镜像没有自定义用户就会以 root 运行）
RUN groupadd -r cloudforge && useradd -r -g cloudforge cloudforge

WORKDIR /app

# 先只复制 pyproject.toml：利用 Docker 层缓存，pyproject 不变时依赖层不会被重建
COPY pyproject.toml ./

# 安装应用依赖（slim 下基本都是预编译 wheel，秒装）
# --no-cache-dir：不保留 pip 下载缓存，减小层体积
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] structlog redis \
    opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-grpc \
    prometheus-fastapi-instrumentator

# 复制源代码（放在依赖安装之后，改代码只重建最后几层）
COPY app/ /app/app/

ENV PYTHONPATH=/app          # 保证 app 包可被 import
ENV PYTHONUNBUFFERED=1       # Python 输出不被缓存，日志实时打到 stdout 供 Loki 采集

USER cloudforge              # 切换到非 root 用户运行

EXPOSE 8000

# 启动命令：用 python -m uvicorn 保证 PYTHONPATH 生效
# 开发环境在 docker-compose.yml 中通过 command: 覆盖加 --reload
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
