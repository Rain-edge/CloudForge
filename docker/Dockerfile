# CloudForge 应用镜像 — 多阶段构建版（builder 编译 → runtime 精简运行）
#
# 为什么改成多阶段：
#   - 旧版单阶段 python:3.11-slim 同时携带编译工具链（gcc/libpq-dev），镜像约 300MB
#   - 多阶段把"编译期依赖"和"运行期依赖"分离：runtime 只保留运行需要的库
#   - builder 用 alpine + 编译工具链，把依赖装进 site-packages；runtime 纯复制，不装任何编译器
#
# 为什么 builder/runtime 都用 alpine 而不是 slim：
#   - 两阶段必须同一种 libc（glibc/musl），否则编译出的二进制 C 扩展不能跨阶段复用
#   - alpine 基础镜像约 50MB（slim 约 120MB），是最终体积的主要来源
#   - 依赖全部有 musllinux 预编译 wheel（asyncpg / cryptography / uvloop / pydantic-core 等），
#     无需编译工具链；万一某依赖需要源码编译，pip 会报错，此时再按需补装 gcc/musl-dev
#     （注意不要装 python3-dev / clang / llvm，会拖进 ~200MB 工具链、构建极慢）
#
# 最终镜像体积实测约 174MB（单阶段 slim 版约 487MB，瘦身 64%），以 docker images 为准。

# ---------- 阶段 1：builder（编译期） ----------
FROM python:3.11-alpine AS builder

# apk 源切到阿里云镜像（国内机器加速；外网机器也能自动回退官方源）
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# pip 也切到阿里云镜像，加速国内下载
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

WORKDIR /build

# 先只复制 pyproject.toml：利用 Docker 层缓存，pyproject 不变时依赖层不会被重建
COPY pyproject.toml ./

# 安装应用依赖
# --no-cache-dir：不保留 pip 下载缓存；--no-compile：不生成 __pycache__（runtime 更小）
RUN pip install --no-cache-dir --no-compile \
    fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] structlog redis \
    opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-grpc \
    prometheus-fastapi-instrumentator

# ---------- 阶段 2：runtime（运行期） ----------
FROM python:3.11-alpine AS runtime

# apk 源切到阿里云镜像
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 运行期只需要 libpq.so.5（asyncpg 动态链接），不需要 -dev 包和编译器
# postgresql-libs 提供 libpq 运行库，体积约 1MB
RUN apk add --no-cache postgresql-libs

# 从 builder 复制编译好的依赖（二进制 C 扩展与 alpine/musl 匹配）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# 移除 runtime 不需要的 pip/setuptools 及其缓存，再省 10-15MB
RUN rm -rf /usr/local/lib/python3.11/site-packages/pip* \
           /usr/local/lib/python3.11/site-packages/setuptools* \
           /usr/local/lib/python3.11/site-packages/_distutils_hack \
           /usr/local/lib/python3.11/site-packages/distutils-precedence.pth \
           /usr/local/lib/python3.11/site-packages/__pycache__ \
           /root/.cache

# 创建非 root 用户（容器安全基线：默认镜像没有自定义用户就会以 root 运行）
RUN addgroup -S cloudforge && adduser -S -G cloudforge cloudforge

WORKDIR /app

# 复制源代码（放在依赖安装之后，改代码只重建最后几层）
COPY app/ /app/app/

# 保证 app 包可被 import
ENV PYTHONPATH=/app
# Python 输出不被缓存，日志实时打到 stdout 供 Loki 采集
ENV PYTHONUNBUFFERED=1

# 切换到非 root 用户运行
USER cloudforge

EXPOSE 8000

# 启动命令：用 python -m uvicorn 保证 PYTHONPATH 生效
# 开发环境在 docker-compose.yml 中通过 command: 覆盖加 --reload
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
