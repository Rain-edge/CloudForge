# CloudForge

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

## 关键设计与实现

- 🔁 **GitOps 闭环** — `git push` → GitHub Actions 构建多架构镜像并把新 tag 写回 chart → ArgoCD 自动同步到 K8s，Git 即生产环境真相源；回滚只需回退代码重新 push
- 📊 **可观测性三支柱打通** — OTel Trace + Prometheus Metrics + Loki Logs，JSON 日志携带 `trace_id`/`span_id`，Grafana 点击日志一键跳转 Tempo 完整调用链（Loki derivedFields 联动）
- 🚀 **生产级韧性** — HPA 自动扩缩容（2-10 副本，实测扩容至 6～7 副本）、PDB 防误删、Liveness/Readiness 分离探针自愈、金丝雀按权重灰度
- 🐳 **轻量安全镜像** — 多阶段构建（builder 编译 → runtime 精简），编译工具链不进运行镜像，非 root 运行，支持 amd64/arm64 双架构
- 📦 **一键部署** — Helm Chart（16 模板）+ 预置 Grafana Dashboard 与 Alertmanager 告警规则

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
# 21 passed
```

### 3. 一键部署到 Kubernetes

```bash
# 创建本地 k3d 集群
bash scripts/setup-k3d.sh

# 预拉 observability 镜像到集群（ghcr.io 国内直连慢，先 docker pull 再 k3d image import，安装不再卡镜像）
bash scripts/preload-images.sh

# 安装可观测性组件（Prometheus + Grafana + Loki + Tempo）
bash scripts/setup-observability.sh

# 构建并导入本地镜像（k3d 集群内不含镜像时会 ImagePullBackOff）
docker build -f docker/Dockerfile -t cloudforge--app:latest .
k3d image import cloudforge--app:latest -c <cluster名>

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
```

之后任何 `git push` 的流程：

1. GitHub Actions 构建 amd64/arm64 双架构镜像，推送 `DockerHub/cloudforge:<short-sha>`
2. CI 把新 `repository`/`tag` 写回 `chart/values.yaml` 并提交（commit 带 `[skip ci]` 防止死循环）
3. ArgoCD 检测到 chart 变更 → 自动同步 → 滚动更新到新版本
4. **回滚 = 回退代码重新 push**，ArgoCD 自动恢复到旧版本，全程零人工干预

> 前提：GitHub 仓库需配置 `DOCKERHUB_USER` / `DOCKERHUB_TOKEN` 两个 Secrets，且 ArgoCD 能访问该仓库（私有仓库需配置 Repository Credentials）。

---

## 技术栈

| 领域 | 选型 | 理由 |
|------|------|------|
| 后端 | Python 3.11, FastAPI | 异步高性能，自动 OpenAPI 文档 |
| 数据库 | PostgreSQL 14 | 成熟可靠，JSONB 支持 |
| 缓存 | Redis 7 | 任务列表缓存（TTL 60s + 写失效，Redis 故障自动降级直读 DB） |
| 容器化 | Docker 多阶段构建 | builder 编译 / runtime 精简，非 root 运行，支持 amd64/arm64（实测 174MB，较单阶段 slim 版 487MB 瘦身 64%） |
| 编排 | Kubernetes (k3s/k3d) | 轻量但完整兼容 K8s API |
| 包管理 | Helm | 一键部署，多环境 values 管理 |
| CI/CD | GitHub Actions + ArgoCD | CI 负责测试构建推送，CD 负责 GitOps 同步 |
| 可观测性 | OTel + Prometheus + Grafana + Loki + Tempo | Traces/Metrics/Logs 三支柱 |
| 告警 | Alertmanager → Webhook | 错误率、延迟、Pod 重启异常告警 |
| 韧性 | HPA, PDB, Liveness/Readiness Probe | K8s 原生自愈 |

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

应用日志格式由 `CF_LOG_FORMAT` 控制（K8s 环境 ConfigMap 注入 `json`，本地开发用 `console`）：

- `app/core/logging.py` 统一配置 structlog：JSON 输出含 `timestamp` / `level` / `event` / `request_id` / `trace_id` / `span_id`
- `RequestIDMiddleware` 为每个请求绑定 `request_id`（响应头 `X-Request-ID` 回传），并从当前 OTel Span 读取 `trace_id` / `span_id` 写入日志
- `scripts/grafana-datasources.yaml` 已配置 Loki `derivedFields`：点击日志行中的 `trace_id` → 自动跳转 Tempo 查看完整调用链
- Trace 导出端点：K8s 环境由 ConfigMap 注入 `OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo.monitoring:4317`（Tempo 在 monitoring namespace，必须 FQDN；短名 `tempo:4317` 在应用所在 namespace 解析不到，会导致 trace 全部丢失并产生导出重试风暴），本地 compose 由 docker-compose.yml 覆盖为 Jaeger

```bash
# 本地验证 JSON 日志（含 trace 字段）：
curl -s http://localhost:8000/tasks | head -1
docker compose logs app | grep trace_id
```

### Alertmanager 告警

PrometheusRule 声明 3 条告警（5xx 错误率 > 5%、p95 延迟 > 1s、Pod 频繁重启），经 Alertmanager 发送到 webhook：

- 演示环境 webhook 默认指向 CloudForge 应用自身的接收端点 `/api/v1/alertmanager`（日志记录收到的告警，可在 Loki 检索 `event=alertmanager_webhook_received` 验证）
- 生产环境通过 `--set alertmanager.webhookUrl=https://qyapi.weixin.qq.com/...` 换成企业微信/钉钉/飞书
- ⚠️ kube-prometheus-stack 的 Alertmanager 不会自动使用 chart 的 Secret：先执行 `bash scripts/setup-alertmanager-webhook.sh` 把 webhook 配置注入其实际使用的 Secret（config-reloader 自动热加载）

```bash
# 验证告警链路（无需真实故障，手动向 Alertmanager 推一条测试告警）：
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager 9093:9093
# 另开终端：
curl -X POST http://localhost:9093/api/v2/alerts -H 'Content-Type: application/json' -d '[
  {"labels":{"alertname":"TestAlert","severity":"warning","service":"cloudforge"}}
]'
# 随后应用日志应出现 alertmanager_webhook_received 记录：
kubectl logs -l app=cloudforge --since=5m | grep alertmanager_webhook_received
```

> 注意：新版 Alertmanager（≥0.27）已移除 v1 API，必须用 `/api/v2/alerts`；
> 应用有多个副本时 webhook 会负载均衡到任意 Pod，检查日志要加 `-l app=cloudforge` 或逐个 Pod 查。

---

## 韧性验证

### 压测（k6）

```bash
# 安装 k6: https://k6.io/docs/get-started/installation/
k6 run scripts/load-test.js -e BASE_URL=http://cloudforge.local \
  --summary-export=summary.json
```

脚本阶段设计：`30s` 预热（20 VU）→ `90s` 主压（50 VU）→ `30s` 收尾，共 2.5 分钟；`50 VU` 即 50 个并发虚拟用户。阈值：`p95 < 500ms`、错误率 `< 1%`，结果可通过 `--summary-export` 落盘留存。

**2026-08-28 实测**（Windows + WSL2 + k3d 环境，两次压测 summary.json 存档于 `docs/experiments/2026-08-28-k6-hpa/`）：

| 指标 | 实测值 | 阈值 | 是否达标 |
|------|--------|------|---------|
| p95 延迟 | 1.57s | <500ms | 未达标（见下） |
| 错误率 | 0.00% | <1% | ✅ |
| 平均延迟 | 737ms | - | - |
| 总请求 / RPS | 3418 / 22.7 | - | - |

> p95 未达标的性能定位（逐层实测，详见 RESULTS.md）：单请求 12-15ms、DB 5ms、Redis 16ms，
> `/health/live` 50 并发 avg 82ms，但 `/tasks` 50 并发 avg 1.6s；裸 asyncpg 60 并发 avg 286ms，
> SQLAlchemy async 层 987ms —— 瓶颈在本机 WSL2/k3d overlay 网络的并发开销 + SQLAlchemy async
> 层 + uvicorn 单 worker 事件循环饱和，非应用代码缺陷（缓存/异步/连接池设计均正确）。
> 首轮压测错误率 4.79% 的根因是 OTel 导出端点配置错误（详见下方可观测性节），修复后归零。

### HPA 扩缩容（实测 2 → 3 → 5 → 6 / 2 → 4 → 5 → 6 → 7）

触发条件：`requests.cpu = 100m`，`targetCPUUtilizationPercentage = 70` → 平均利用率达到 **70m**（所有副本 CPU 用量的均值 / requests 总量）即触发扩容。

```bash
# 终端 A：观察 HPA
kubectl get hpa cloudforge -w
# 终端 B：跑压测
k6 run scripts/load-test.js -e BASE_URL=http://cloudforge.local

# 实测过程（详见 docs/experiments/2026-08-28-k6-hpa/RESULTS.md）：
#   CPU 从 4% 飙到 152%～168% → HPA 自动扩容
#   两轮实测扩容路径：2 → 3 → 5 → 6（CPU 峰值 152%）
#                    2 → 4 → 5 → 6 → 7（CPU 峰值 168%）
#   扩容步长由 HPA 算法决定（desired = ceil(当前利用率/目标 × 当前副本)），
#   不是固定逐级 +2
#   压测结束 CPU 回落 → 副本冷却缩回 2（缩容稳定窗口为 K8s 默认 300s，
#   实测缩回 2 约需 6～9 分钟）
```

全程无需人工干预：扩容/缩容由 HPA 控制器根据指标自动完成。

### 金丝雀发布

```bash
# 部署 canary 版本（weight=10：10% 流量进入新版本）
helm upgrade cloudforge ./chart --set canary.enabled=true --set canary.weight=10

# 逐步提升流量
helm upgrade cloudforge ./chart --set canary.weight=50
helm upgrade cloudforge ./chart --set canary.weight=100

# 验证通过 → 转正：把 canary tag 提升为主版本后关掉 canary
helm upgrade cloudforge ./chart --set canary.enabled=false,image.tag=<新版本sha>
```

**异常回滚（秒级摘流）**：

```bash
# 方式一（推荐）：金丝雀 weight 归零，nginx 配置热更新，秒级不再转发流量
helm upgrade cloudforge ./chart --set canary.weight=0

# 方式二：彻底移除金丝雀资源（Deployment + Service + Ingress 一起删）
helm upgrade cloudforge ./chart --set canary.enabled=false
```

> ⚠️ 不要用 `kubectl delete deployment cloudforge-canary` 回滚：
> canary Service 与 Ingress 的 `canary-weight` 注解仍保留，nginx 会把流量转发给
> 已经没有 Pod 的 Service → 后端为空 → **502**。回滚必须通过 helm 把 weight 归零或移除 canary 资源。

**2026-08-28 实测**（nginx ingress 逐请求计数，证据见 docs/experiments/2026-08-28-k6-hpa/RESULTS.md）：

| 权重 | canary 实收 | 比例 |
|------|------------|------|
| 10% | 10/100 | 10% ✅ |
| 50% | 48/100 | 48% ✅ |
| 100% | 50/50 | 100% ✅ |
| 回滚 100→0 | helm upgrade 1.0s，摘流 ≤2s | 0 错误 ✅ |

> 前提：主 Service 的 selector 必须精确匹配（`app=cloudforge, component=stable`）。
> 若只按 `app=cloudforge` 选择，canary Pod 会被主 Service 一并选中，权重分流严重失真
> （实测 weight=10 时 canary 实收 33%～66%）。

### Pod 故障自愈

- Liveness 探针（`/health/live`）：只检查进程存活，不依赖外部服务 —— DB 抖动时不会误杀 Pod
- Readiness 探针（`/health`）：检查 DB 连通性，失败即从 Service 摘流
- PDB（`minAvailable: 1`）：节点维护/驱逐时至少保留 1 个副本，避免全部 Pod 同时被杀

---

## 项目结构

```
cloudforge/
├── app/                        # FastAPI 微服务
│   ├── core/                   # 配置、数据库、日志、缓存、遥测、指标
│   ├── models/                 # SQLAlchemy ORM
│   ├── schemas/                # Pydantic DTO
│   ├── routers/                # API 路由（health, tasks, alerts）
│   ├── middleware/             # RequestID, structlog, trace_id 注入
│   └── tests/                  # pytest + httpx (21 tests: health, tasks, metrics, logging, alerts, cache)
├── alembic/                    # 数据库迁移（alembic）
│   ├── versions/
│   └── env.py
├── chart/                      # Helm Chart
│   ├── templates/              # 16 templates (Deployment, Service, Ingress, HPA, PDB, Grafana CM...)
│   ├── dashboards/             # Grafana 看板 JSON（打包进 ConfigMap）
│   └── values.yaml
├── argocd/                     # ArgoCD Application 定义
├── dashboards/                 # Grafana 看板 JSON（开发和手动导入）
├── scripts/                    # k3d 集群、镜像预拉、可观测性安装、压测、values 更新、E2E验证
├── docker/                     # Dockerfile（多阶段构建：builder 编译 → runtime 精简）
├── .github/workflows/          # GitHub Actions CI（validate → test → build-push → manifest → bump values）
├── docs/                       # 架构决策记录 (ADR)、排障手册 (RUNBOOK)
├── docker-compose.yml          # 本地开发环境
└── pyproject.toml
```

---

## License

MIT
