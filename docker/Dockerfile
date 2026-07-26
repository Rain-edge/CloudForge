# ──────────────────────────────────────────────────────────
# CloudForge Docker 镜像 — 多阶段构建
# =====================================
# 阶段 1 (builder)：安装构建依赖 + 编译 Python C 扩展（asyncpg, bcrypt 等）
# 阶段 2 (runtime)：仅复制编译好的包 + 运行时库，生成最小镜像
#
# 为什么用 Alpine？
#   - 镜像体积小（~80MB vs ~300MB slim）
#   - 攻击面小（仅安装必要的 libpq 运行时库）
#   - 与 Kubernetes 资源限制的哲学一致
#
# 为什么统一两个阶段都用 Alpine？
#   - Python C 扩展（.so）编译时链接 libc
#   - slim 镜像用 glibc，alpine 用 musl — 两者 ABI 不兼容
#   - 跨 libc 复制 .so 文件会导致 ImportError！必须统一 libc 版本
# ──────────────────────────────────────────────────────────

# ===== 构建阶段 =====
FROM python:3.11-alpine AS builder

# 换阿里云镜像源加速 apk 下载
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 安装 C 编译工具链（gcc, musl-dev）和 Python C 扩展所需的头文件
# - postgresql-dev：asyncpg 需要 libpq-fe.h 头文件
# - libffi-dev：cryptography 需要 FFI 头文件
RUN apk add --no-cache gcc musl-dev libffi-dev postgresql-dev

WORKDIR /app

# 先只复制 pyproject.toml，利用 Docker 层缓存：
#   只要依赖不变，pip install 就不会重新执行
COPY pyproject.toml ./

# pip 换阿里云镜像源加速下载
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# --target=/app/deps：将所有包安装到 /app/deps 目录
# 后续 COPY 到 runtime 阶段，避免残留构建工具
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] structlog redis \
    opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-grpc \
    prometheus-fastapi-instrumentator \
    --target=/app/deps


# ===== 运行阶段 =====
FROM python:3.11-alpine AS runtime

# 创建非 root 用户（安全最佳实践）
RUN addgroup -S cloudforge && adduser -S cloudforge -G cloudforge

# libpq：PostgreSQL C 客户端库的运行时部分（asyncpg 在运行时需要）
# 仅 500KB，远小于 postgresql-dev（包含头文件和静态库）
RUN apk add --no-cache libpq

# 从 builder 复制已编译的 Python 包
COPY --from=builder /app/deps /usr/local/lib/python3.11/site-packages/

# 复制应用源代码（.dockerignore 已排除 tests/chart/docs 等无关文件）
COPY app/ /app/app/

# Python 路径：让 uvicorn 能找到 app.main 模块
ENV PYTHONPATH=/app
# 不缓冲输出，确保日志立即出现在 docker logs 中
ENV PYTHONUNBUFFERED=1

# 切换到非 root 用户
USER cloudforge

# FastAPI 默认端口
EXPOSE 8000

# 启动命令：uvicorn ASGI 服务器
# --host 0.0.0.0：监听所有网络接口（容器内必须）
# --port 8000：与 EXPOSE 一致
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
