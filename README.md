# CloudForge 🏗️

**云原生全栈微服务运维平台** — 从代码到 Kubernetes 生产部署，自带可观测性与 CI/CD 的实战项目。

> 面向云计算方向实习求职，重点展示 GitOps、可观测性、容器编排三项核心能力。

---

## 架构

```
GitHub → GitHub Actions (CI) → Docker Hub
                                    ↓
          ArgoCD (GitOps) → Kubernetes (k3s)
                                    ↓
          Ingress Nginx → FastAPI (HPA 2-10) → PostgreSQL + Redis
                                    ↓
          Prometheus + Grafana + Loki + Tempo + Alertmanager
```

---

## 快速开始

### 1. 本地开发（Docker Compose）

```bash
# 启动全部服务
docker compose up -d

# 验证
curl http://localhost:8000/health
# → {"status":"ok","db":"connected"}

# Swagger 文档
open http://localhost:8000/docs
```

### 2. 运行测试

```bash
pip install -e ".[dev]"
pytest app/tests -v
# 10 passed
```

### 3. 部署到 Kubernetes

```bash
# 创建本地 k3d 集群
bash scripts/setup-k3d.sh

# 安装可观测性组件
bash scripts/setup-observability.sh

# 安装基础设施依赖
helm install postgresql oci://registry-1.docker.io/bitnamicharts/postgresql \
  --set auth.database=cloudforge --set auth.username=cloudforge
helm install redis oci://registry-1.docker.io/bitnamicharts/redis

# 部署 CloudForge
helm install cloudforge ./chart

# 暴露服务
kubectl port-forward svc/cloudforge 8000:8000
```

### 4. GitOps（ArgoCD）

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/cloudforge-app.yaml

# 之后任何 git push 会自动被 ArgoCD 同步到 K8s
```

---

## 技术栈

| 领域 | 选型 | 理由 |
|------|------|------|
| 后端 | Python 3.11, FastAPI | 异步高性能，自动 OpenAPI 文档 |
| 数据库 | PostgreSQL 14 | 成熟可靠，JSONB 支持 |
| 缓存 | Redis 7 | 高性能缓存（预留为 Celery Broker） |
| 容器化 | Docker multi-stage | 镜像 < 100MB，非 root 运行 |
| 编排 | Kubernetes (k3s/k3d) | 轻量但完整兼容 K8s API |
| 包管理 | Helm | 一键部署，多环境 values 管理 |
| CI/CD | GitHub Actions + ArgoCD | CI 负责测试构建推送，CD 负责 GitOps 同步 |
| 可观测性 | OTel + Prometheus + Grafana + Loki + Tempo | Traces/Metrics/Logs 三支柱 |
| 告警 | Alertmanager → Webhook | 错误率、延迟、Pod 重启异常告警 |
| 韧性 | HPA, PDB, Readiness/Liveness Probe | K8s 原生自愈 |

---

## 可观测性

启动后访问：

```bash
# Grafana（默认 admin/admin）
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80

# Jaeger（本地开发 Trace 查看）
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
```

预置 Dashboard：
- `dashboards/cloudforge-overview.json` — 应用级：QPS、延迟、错误率
- `dashboards/cloudforge-k8s.json` — 集群级：CPU、内存、副本数、重启次数

---

## 韧性验证

### 压测

```bash
# 安装 k6: https://k6.io/docs/get-started/installation/
k6 run scripts/load-test.js -e BASE_URL=http://cloudforge.local
```

### 金丝雀发布

```bash
# 部署 canary 版本
helm upgrade cloudforge ./chart --set canary.enabled=true --set canary.weight=10

# 逐步提升流量
helm upgrade cloudforge ./chart --set canary.weight=50
helm upgrade cloudforge ./chart --set canary.weight=100

# 异常回滚：直接删除 canary deployment
kubectl delete deployment cloudforge-canary
```

### HPA 扩缩容

```bash
# 观察 HPA
kubectl get hpa cloudforge -w

# 触发扩容：跑压测观察副本数从 2 增长
```

---

## 项目结构

```
cloudforge/
├── app/                        # FastAPI 微服务
│   ├── core/                   # 配置、数据库、遥测、指标
│   ├── models/                 # SQLAlchemy ORM
│   ├── schemas/                # Pydantic DTO
│   ├── routers/                # API 路由（health, tasks）
│   ├── middleware/             # RequestID, structlog, trace_id 注入
│   └── tests/                  # pytest + httpx
├── alembic/                    # 数据库迁移（alembic）
│   ├── versions/
│   └── env.py
├── chart/                      # Helm Chart
│   ├── templates/              # Deployment, Service, Ingress, HPA, PDB...
│   └── values.yaml
├── argocd/                     # ArgoCD Application 定义
├── dashboards/                 # Grafana 看板 JSON
├── scripts/                    # k3d 集群、可观测性安装、压测脚本
├── docker/                     # Dockerfile（多阶段构建）
├── .github/workflows/          # GitHub Actions CI
├── docs/                       # 架构决策记录 (ADR)
├── docker-compose.yml          # 本地开发环境
└── pyproject.toml
```

---

## 已知局限与改进方向

- 🟡 PostgreSQL 单点部署，未配置主从复制和备份策略
- 🟡 Redis 单实例（生产应配置集群）
- 🟡 未实现 JWT 鉴权，API 端点无认证保护
- 🟡 Secret 管理使用明文 Secret（生产应使用 Sealed Secrets 或 External Secrets Operator）
- 🟡 金丝雀发布依赖手动调整权重，未集成 Argo Rollouts 实现自动化渐进式交付
- 🟡 未配置 NetworkPolicy 实现微服务间零信任网络
- 🔮 后续方向：Terraform 云资源管理、多集群联邦、服务网格（Istio/Linkerd）

---

## 证书

MIT
