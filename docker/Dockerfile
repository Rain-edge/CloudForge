# ──────────────────────────────────────────────────────────
# CloudForge Docker 镜像 — 简化构建（slim 基准）
# =====================================
# 为什么用 slim 而不是 alpine？
#   - slim (Debian) 有预编译的 Python C 扩展 wheel
#   - asyncpg、bcrypt 等包直接 pip install 二进制，无需编译
#   - 构建时间：30s vs alpine 的 5-10min
#   - 镜像体积 ~300MB，仍然合理
# ──────────────────────────────────────────────────────────

FROM python:3.11-slim

<<<<<<< HEAD
# apt 换阿里云源（Debian 官方源国内慢）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# pip 换阿里云源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# libpq-dev：asyncpg 运行时需要 PostgreSQL 客户端库
RUN apt-get update -qq && apt-get install -y -qq libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r cloudforge && useradd -r -g cloudforge cloudforge
=======
# 换阿里云镜像源加速 apk 下载
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 安装 C 编译工具链（gcc, musl-dev）和 Python C 扩展所需的头文件
# - postgresql-dev：asyncpg 需要 libpq-fe.h 头文件
# - libffi-dev：cryptography 需要 FFI 头文件
RUN apk add --no-cache gcc musl-dev libffi-dev postgresql-dev
>>>>>>> 50bfac1 (？？？)

WORKDIR /app

# 先只复制 pyproject.toml，利用 Docker 层缓存
COPY pyproject.toml ./

<<<<<<< HEAD
# 安装依赖（slim 下有预编译 wheel，秒装）
=======
# pip 换阿里云镜像源加速下载
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# --target=/app/deps：将所有包安装到 /app/deps 目录
# 后续 COPY 到 runtime 阶段，避免残留构建工具
>>>>>>> 50bfac1 (？？？)
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] structlog redis \
    opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-grpc \
    prometheus-fastapi-instrumentator

# 复制应用源代码
COPY app/ /app/app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER cloudforge

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
