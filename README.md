# CloudForge 🏗️

**云原生全栈微服务运维平台** — 从代码到 Kubernetes 生产部署，自带可观测性与 CI/CD 的实战项目。

> 面向云计算方向实习求职，重点展示 **GitOps、可观测性、容器编排** 三项核心能力。

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Kubernetes](https://img.shields.io/badge/K8s-k3s/k3d-326CE5?logo=kubernetes&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-Chart-0F1689?logo=helm&logoColor=white)
![ArgoCD](https://img.shields.io/badge/ArgoCD-GitOps-EF7B4D?logo=argo-cd&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6526C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?logo=grafana&logoColor=white)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=github-actions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 亮点

- 🔁 **GitOps 闭环** — `git push` → GitHub Actions 构建多架构镜像 → ArgoCD 自动同步到 K8s，Git 即生产环境真相源
- 📊 **可观测性三支柱打通** — OTel Trace + Prometheus Metrics + Loki Logs，日志点击 `trace_id` 一键跳转 Tempo 完整调用链
- 🚀 **生产级韧性** — HPA 自动扩缩容（2-10 副本）、PDB 防误删、Liveness/Readiness Probe 自愈、金丝雀按权重灰度
- 🐳 **轻量安全镜像** — 多阶段构建，alpine runtime + 非 root 运行，镜像 < 100MB，支持 amd64/arm64 双架构
- 📦 **一键部署** — Helm Chart（15 模板）+ 预置 Grafana Dashboard 与 Alertmanager 告警规则

---

## 目录

- [架构](#架构)
- [快速开始](#快速开始)
- [技术栈](#技术栈)
- [可观测性](#可观测性)
- [韧性验证](#韧性验证)
- [项目结构](#项目结构)
- [License](#license)

---

## 架构

```
GitHub ──► GitHub Actions (CI) ──► Docker Hub (multi-arch image)
                                        │
                                        ▼
   Git repo ──► ArgoCD (GitOps) ──► Kubernetes (k3s)
                                        │
                                        ▼
   Ingress Nginx ──► FastAPI (HPA 2-10) ──► PostgreSQL + Redis
                                        │
                                        ▼
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
# 14 passed
```

### 3. 一键部署到 Kubernetes

```bash
# 创建本地 k3d 集群
bash scripts/setup-k3d.sh

# 安装可观测性组件（Prometheus + Grafana + Loki + Tempo）
bash scripts/setup-observability.sh

# 一键部署 CloudForge（含 PostgreSQL + Redis 依赖）
helm dependency update ./chart
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
| 容器化 | Docker multi-stage | 最终镜像 < 100MB (alpine runtime)，非 root 运行 |
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

# Tempo（Traces）
kubectl port-forward -n monitoring svc/tempo 16686:16686

# Jaeger（本地开发 Trace 查看）
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
```

### 预置 Grafana Dashboard

两个预置 Dashboard 通过 Helm 部署时自动导入 Grafana（利用 kube-prometheus-stack 的 sidecar）：

- `cloudforge-overview` — **应用级**：QPS、错误率（5xx 占比）、p95 延迟、状态码分布
- `cloudforge-k8s` — **集群级**：CPU 使用率、内存占用、副本数（desired vs available）、Pod 重启频率

手动导入：从 `dashboards/` 目录上传 JSON 文件到 Grafana UI（Dashboards → Import）。

### 日志-Trace 关联

应用日志在 K8s 环境输出 JSON 格式，每条日志包含 `trace_id` 和 `span_id` 字段。在 Grafana 中：

1. Loki 自动采集容器 stdout（通过 Promtail）
2. 点击日志行中的 `trace_id` → Grafana 自动跳转到 Tempo 查看完整 Trace
3. 本地开发使用 `CF_LOG_FORMAT=console`（可读格式），K8s 默认 `CF_LOG_FORMAT=json`

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
│   └── tests/                  # pytest + httpx (14 tests: health, tasks, metrics, logging)
├── alembic/                    # 数据库迁移（alembic）
│   ├── versions/
│   └── env.py
├── chart/                      # Helm Chart
│   ├── templates/              # 15 templates (Deployment, Service, Ingress, HPA, PDB, Grafana CM...)
│   ├── dashboards/             # Grafana 看板 JSON（打包进 ConfigMap）
│   └── values.yaml
├── argocd/                     # ArgoCD Application 定义
├── dashboards/                 # Grafana 看板 JSON（开发和手动导入）
├── scripts/                    # k3d 集群、可观测性安装、压测脚本、E2E验证
├── docker/                     # Dockerfile（多阶段构建：builder → alpine runtime, < 100MB）
├── .github/workflows/          # GitHub Actions CI（validate → test → build-push → manifest）
├── docs/                       # 架构决策记录 (ADR)
├── docker-compose.yml          # 本地开发环境
└── pyproject.toml
```

---

## License

MIT
