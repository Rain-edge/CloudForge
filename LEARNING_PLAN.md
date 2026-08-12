# CloudForge 学习计划

## 项目全貌

这是一个云原生微服务运维平台的完整演示项目，覆盖从本地开发到 Kubernetes 生产部署的全流程。关键是理解它串联起来的每一项技术为什么存在、解决什么问题。

---

## 第一周：FastAPI 应用本身（Python 后端）

### 学习目标
理解这个微服务的核心代码是怎么写的。

### 文件顺序
| 顺序 | 文件 | 学什么 |
|------|------|--------|
| 1 | `app/main.py` | FastAPI 生命周期（lifespan）、路由注册、中间件加载顺序 |
| 2 | `app/core/config.py` | pydantic-settings 环境变量管理（CF_ 前缀自动映射） |
| 3 | `app/core/database.py` | SQLAlchemy 2.0 异步引擎、连接池参数（pool_size/recycle/pre_ping） |
| 4 | `app/models/task.py` | ORM 模型定义、UUID 主键、server_default 时间戳 |
| 5 | `app/schemas/task.py` | Pydantic v2 DTO 模式：请求体校验 vs 响应序列化 |
| 6 | `app/routers/tasks.py` | RESTful 五件套（CRUD）、async/await 写法、依赖注入 get_db |
| 7 | `app/routers/health.py` | 健康检查端点，为什么 K8s 需要它（liveness/readiness probe） |

### 动手
```powershell
# 本地无 Docker 跑（纯 Python）
pip install fastapi uvicorn sqlalchemy aiosqlite
cd app
uvicorn main:app --reload
```

### 检验标准
- 能用 curl 调通所有 CRUD 端点
- 能解释 `Depends(get_db)` 的作用
- 能画出一张 Pydantic 数据流图：请求体 → TaskCreate → ORM Task → TaskResponse → 响应体

---

## 第二周：容器化 + Docker Compose

### 学习目标
理解为什么要容器化，以及多服务之间如何通信。

### 文件
| 顺序 | 文件 | 学什么 |
|------|------|--------|
| 1 | `docker/Dockerfile` | 多阶段构建、slim vs alpine 选型、非 root 用户 |
| 2 | `docker-compose.yml` | 三个服务的依赖编排（depends_on）、健康检查（healthcheck）、环境变量注入 |
| 3 | `.dockerignore` | 哪些文件不打包进镜像 |

### 动手
```powershell
docker compose up -d
docker compose logs -f app
docker compose down -v
```

### 检验标准
- 能解释容器里 `postgres` 这个名字为什么能代替 localhost
- 能说出 healthcheck 在 depends_on 中起什么作用
- 能手动 `docker build` 并运行单个容器

---

## 第三周：Kubernetes + Helm

### 学习目标
理解 K8s 资源对象如何对应 Docker Compose 的概念。

### 文件
| 顺序 | 文件/目录 | 学什么 |
|------|-----------|--------|
| 1 | `chart/Chart.yaml` | Helm Chart 元数据版本管理 |
| 2 | `chart/values.yaml` | 参数化配置：镜像名、副本数、资源限制、HPA 参数 |
| 3 | `chart/templates/deployment.yaml` | Deployment：副本数、probe、资源限制、envFrom |
| 4 | `chart/templates/service.yaml` | Service：ClusterIP/LoadBalancer、port 映射 |
| 5 | `chart/templates/hpa.yaml` | HPA：CPU 利用率阈值触发自动扩缩容 |
| 6 | `chart/templates/secret.yaml` + `configmap.yaml` | 敏感/非敏感配置分离 |
| 7 | `chart/templates/postgres.yaml` + `redis.yaml` | 手写 K8s Deployment + Service（不等同于 Docker Compose 的 depends_on） |

### 动手
```powershell
kubectl get pods -w
kubectl describe pod cloudforge-xxx
kubectl logs cloudforge-xxx
kubectl exec -it cloudforge-pg-xxx -- psql -U cloudforge
```

### 检验标准
- 能说清楚 Deployment、Service、Pod 三者之间的关系
- 能解释 `kubectl port-forward` 的工作原理
- 能把 HPA 的 `targetCPUUtilizationPercentage: 70` 和压测结果联系起来

---

## 第四周：可观测性三大支柱

### 概念对照
```
Logging   → structlog（app/middleware/logging.py）
          → 每条日志带 request_id / trace_id
          → Loki 采集容器 stdout

Metrics   → Prometheus（app/core/metrics.py）
          → /metrics 端点暴露 HTTP 请求计数、延迟
          → Grafana Dashboard 可视化

Tracing   → OpenTelemetry（app/core/telemetry.py）
          → 自动插桩 FastAPI 路由 + SQLAlchemy 查询
          → Tempo 存储 Trace，Grafana 中日志跳转 Trace
```

### 文件
| 顺序 | 文件 | 学什么 |
|------|------|--------|
| 1 | `app/core/metrics.py` | Prometheus 指标：Counter/Gauge/Histogram 的区别 |
| 2 | `app/core/telemetry.py` | OpenTelemetry：TracerProvider → SpanProcessor → Exporter 链路 |
| 3 | `app/middleware/logging.py` | structlog contextvars、X-Request-ID 注入、trace_id 关联 |
| 4 | `dashboards/cloudforge-overview.json` | Grafana JSON 模型如何定义面板和 PromQL |
| 5 | `chart/templates/prometheusrule.yaml` | Prometheus Alert 规则：expr/for/labels/annotations |

### 动手
```powershell
# Grafana 中操作：
# 1. Explore → 选 Prometheus 数据源 → 输入 http_requests_total
# 2. Dashboards → cloudforge-overview → 观察 QPS/延迟/错误率
# 3. 配合 k6 压测，实时看 Grafana 面板变化
```

### 检验标准
- 能说出 Counter 和 Histogram 分别适合什么场景
- 能在 Grafana Explore 里手写 PromQL：`rate(http_requests_total{status="200"}[1m])`
- 能解释日志里的 trace_id 怎么和 Tempo 里的 Trace 关联

---

## 第五周：CI/CD + GitOps 理念

### 概念理解（不需要本地跑）
```
GitHub Actions (CI)  → 测试 → 构建镜像 → 推送到 Docker Hub
ArgoCD (CD)           → 监听 Git 仓库 → 自动同步到 K8s
```

### 文件
| 顺序 | 文件 | 学什么 |
|------|------|--------|
| 1 | `.github/workflows/` | CI 流水线：validate → test → build-push → manifest |
| 2 | `argocd/cloudforge-app.yaml` | ArgoCD Application 定义：source repo + destination cluster |
| 3 | `chart/templates/ingress.yaml` | Ingress 对外暴露服务 |

### 检验标准
- 能说出 CI 和 CD 的分工界线
- 能解释 GitOps 的核心思想：Git 是唯一真相源
- 能说出 ArgoCD 的 sync 和 self-heal 机制

---

## 知识点速查表

| 概念 | 在哪里体现 | 一句话解释 |
|------|-----------|-----------|
| 异步数据库 | SQLAlchemy async engine + asyncpg | 不用等上一个 SQL 完成就能发下一个 |
| 连接池 | pool_size / max_overflow | 复用数据库连接，避免每次请求新建 TCP 连接 |
| 环境变量优先级 | pydantic-settings CF_ 前缀 | 代码默认值 < .env 文件 < 系统环境变量 |
| 依赖注入 | FastAPI Depends(get_db) | 框架自动管理对象的创建和销毁 |
| 健康检查 | /health → livenessProbe / readinessProbe | K8s 根据探针结果决定是否重启或引流 |
| HPA | chart/templates/hpa.yaml | CPU 超过 70% 自动加副本，低于阈值逐步缩减 |
| 无头服务 | Service type: ClusterIP | 集群内部用服务名通信，不暴露到外网 |
| 配置分离 | ConfigMap（明文） + Secret（敏感） | 不改代码就能改配置 |

---

## 推荐节奏

- **每天 1-2 小时**，按上面的顺序逐个文件精读
- **每读完一个文件**，在终端里跑相关命令验证理解
- **每周末**，不看代码，能画出一张架构图 + 一句说明每个组件做什么
- **最后一周**，把整个流程从 `docker compose up` 到 k6 压测不看笔记独立跑一遍
