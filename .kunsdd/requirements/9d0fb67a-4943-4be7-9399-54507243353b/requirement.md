# CloudForge - 云原生微服务运维平台

## 背景

当前中小团队（3-10 人）的微服务交付普遍存在以下痛点：

- 上线依赖人工操作（scp/手动重启），流程不可重复、不可审计
- 缺乏统一的可观测性，故障发现靠用户报修而非主动告警
- CI/CD 与 K8s 部署割裂，代码合并后需要手动触发更新

本项目面向一位虚构的 3 人创业团队场景：他们维护一个 SaaS 应用，需要一套从代码提交到生产部署、附带自动监控告警的标准化交付体系。项目同时作为个人云计算方向实习作品，重点展示 GitOps、可观测性、容器编排三项核心能力。

## 目标

1. **极简微服务**：使用 FastAPI 实现一个 Task Manager CRUD 服务，作为被管理对象。（JWT 鉴权标记为后续迭代，当前版本为开放 API。）
2. **GitOps 交付流水线**：GitHub Actions 触发测试 → 构建多架构镜像 → 推送 Docker Hub → ArgoCD 自动同步到 K8s，支持金丝雀发布配置。
3. **统一可观测性**：OpenTelemetry SDK 埋点（Traces + Metrics + Logs），Prometheus + Grafana + Loki + Tempo 四件套，Grafana 看板导入自动化。
4. **基础设施即代码**：k3d 脚本创建本地集群，Helm Chart 打包所有服务，一条命令部署。（Terraform 云资源管理标记为后续迭代。）
5. **韧性验证**：HPA 自动扩缩容、PodDisruptionBudget、优雅关闭、健康检查；压测脚本（k6），金丝雀发布流量切分配置。

## 非目标（明确不做）

- 不实现完整的用户中心/注册登录系统（JWT 鉴权标记为后续迭代）
- 不手动二进制部署 K8s（改用 k3s/k3d，把时间投入更区分度的工作）
- 不实现真实邮件发送（Celery 异步任务标记为后续迭代）
- 不做多租户/计费系统
- 不做 Terraform 云资源管理（当前使用 k3d 本地集群脚本）
- 不做混沌工程演练（标记为后续迭代）

## 技术选型与理由

| 领域 | 选型 | 理由 |
|------|------|------|
| 后端框架 | Python 3.10+, FastAPI | 异步高性能，自动 OpenAPI 文档，Pydantic 类型安全 |
| 数据库 | PostgreSQL 14 | 成熟可靠，支持 JSONB，生态好 |
| 缓存 | Redis 7 | 演示环境使用（Celery Broker 标记为后续） |
| 容器化 | Docker multi-stage | 最终镜像 < 100MB，非 root 运行 |
| 编排 | Kubernetes (k3s 本地/k3d 模拟) | 轻量但完整兼容 K8s API |
| 包管理 | Helm | 一键部署，values 多环境管理 |
| CI/CD | GitHub Actions + ArgoCD | Actions 负责 CI（测试+构建+推送），ArgoCD 负责 CD（GitOps 同步） |
| 可观测性 | OpenTelemetry + Prometheus + Grafana + Loki + Tempo | 统一 Traces/Metrics/Logs 三支柱 |
| 告警 | Alertmanager → Webhook | 错误率 > 5% 或 Pod 重启频率异常触发 |
| 基础设施 | k3d 脚本 | 一条命令创建本地 K8s 集群 |
| 韧性 | HPA, PDB, Readiness/Liveness Probe, Graceful Shutdown | K8s 原生自愈能力 |

## 架构概览

```
                    ┌──────────────┐
                    │   GitHub     │
                    │  (源代码)     │
                    └──────┬───────┘
                           │ git push
                    ┌──────▼───────┐
                    │ GitHub Actions│
                    │ 测试+构建+推送 │
                    └──────┬───────┘
                           │ docker push + manifest update
              ┌────────────▼──────────────┐
              │       ArgoCD (GitOps)      │
              │  监控 Git Repo 自动同步     │
              └────────────┬──────────────┘
                           │ apply
              ┌────────────▼──────────────┐
              │    Kubernetes (k3s)        │
              │                            │
              │  ┌──────────────────────┐  │
              │  │ Ingress Nginx        │  │
              │  │ (Canary 流量切分)     │  │
              │  └─────────┬────────────┘  │
              │            │               │
              │  ┌─────────▼───────────┐   │
              │  │  FastAPI (HPA 2-10) │   │
              │  │  Task Manager CRUD  │   │
              │  └──┼──────────────────┘   │
              │     │                       │
              │  ┌──┴──────────┐           │
              │  │ PostgreSQL  │  Redis    │
              │  └─────────────┘           │
              │                            │
              │  ┌──────────────────────┐  │
              │  │ Observability Stack  │  │
              │  │ Prometheus + Grafana │  │
              │  │ Loki + Tempo         │  │
              │  │ Alertmanager         │  │
              │  └──────────────────────┘  │
              └────────────────────────────┘
```

## 项目结构

```
cloudforge/
├── app/                              # FastAPI 微服务
│   ├── main.py                       # 应用工厂 + lifespan
│   ├── core/                         # 配置、数据库、遥测、指标
│   │   ├── config.py                 # pydantic-settings 环境变量
│   │   ├── database.py               # 异步 SQLAlchemy 引擎
│   │   ├── telemetry.py              # OpenTelemetry (OTLP → Tempo)
│   │   └── metrics.py                # Prometheus /metrics endpoint
│   ├── models/task.py                # Task ORM (UUID, title, status)
│   ├── schemas/task.py               # Pydantic v2 请求/响应
│   ├── routers/{health,tasks}.py     # /health + CRUD /tasks
│   ├── middleware/logging.py         # RequestID + structlog
│   └── tests/                        # pytest + httpx (10 tests)
├── chart/                            # Helm Chart
│   ├── Chart.yaml / values.yaml
│   └── templates/                    # 13 个模板
│       ├── deployment.yaml           # non-root, readonly FS, probes
│       ├── service.yaml              # ClusterIP
│       ├── ingress.yaml              # 主 Ingress
│       ├── ingress-canary.yaml       # Canary Ingress
│       ├── configmap.yaml / secret.yaml
│       ├── hpa.yaml                  # CPU 70%, min 2 max 10
│       ├── pdb.yaml                  # minAvailable 1
│       ├── servicemonitor.yaml       # Prometheus 自动发现
│       ├── prometheusrule.yaml       # 3 条告警规则
│       └── alertmanager-config.yaml  # Webhook 接收器
├── argocd/cloudforge-app.yaml        # ArgoCD Application
├── dashboards/                       # Grafana 看板 JSON
│   ├── cloudforge-overview.json      # 应用级 (QPS/延迟/错误率)
│   └── cloudforge-k8s.json           # 集群级 (CPU/内存/副本/重启)
├── scripts/                          # 辅助脚本
│   ├── setup-k3d.sh                  # 创建 k3s 集群
│   ├── setup-observability.sh        # 安装 Prometheus + Grafana + Loki + Tempo
│   ├── load-test.js                  # k6 压测 (50 VUs)
│   └── verify.py                     # E2E 验证脚本
├── .github/workflows/ci.yml          # GitHub Actions CI
├── docker/Dockerfile                 # 多阶段构建 (slim → alpine)
├── docker-compose.yml                # 本地开发环境
├── docs/adr/                         # 架构决策记录 (3 篇)
├── README.md
├── ROADMAP.md
└── pyproject.toml
```

## 验收标准

### M1: 本地开发环境

- [ ] `docker compose up` 一键启动 PostgreSQL + Redis + FastAPI
- [ ] `/docs` 可访问 Swagger 文档
- [ ] `/health` 返回健康状态（含 DB 连接状态）
- [ ] `/metrics` 返回 Prometheus 指标（40+ metric lines）
- [ ] CRUD 接口通过 pytest 测试（10/10 green）

### M2: 容器化与 CI

- [ ] Docker 多阶段构建，镜像 < 100MB
- [ ] GitHub Actions 在 push 时自动跑测试
- [ ] 测试通过后自动构建镜像并推送 Docker Hub
- [ ] 支持 linux/amd64 和 linux/arm64 多架构

### M3: K8s 部署与 GitOps

- [ ] `scripts/setup-k3d.sh` 一键创建 k3d 集群
- [ ] `helm install cloudforge ./chart` 部署全部服务
- [ ] ArgoCD 安装并配置，监听 Git Repo 自动同步
- [ ] Ingress 路由正常，Canary 流量切分配置可用

### M4: 可观测性

- [ ] OpenTelemetry 自动埋点：FastAPI + SQLAlchemy 全量 Tracing
- [ ] Prometheus 采集应用指标（/metrics endpoint, ServiceMonitor）
- [ ] Grafana 看板导入后可视化（2 个预置 Dashboard JSON）
- [ ] Loki + Promtail 采集日志，Tempo 接收 Traces
- [ ] Alertmanager 规则：错误率 > 5%、高延迟、Pod 频繁重启

### M5: 韧性验证

- [ ] HPA 基于 CPU 自动扩缩容（min 2, max 10）
- [ ] PDB 确保最小可用 Pod 数（minAvailable 1）
- [ ] Readiness/Liveness Probe 正确配置（/health endpoint）
- [ ] 优雅关闭：terminationGracePeriodSeconds=30
- [ ] 压测脚本：k6 4 阶段 ramp-up（20→50→50→0 VUs）
- [ ] 金丝雀发布：Ingress Nginx Canary annotations 流量切分配置

### M6: 文档

- [ ] README 包含架构图、快速开始、模块说明
- [ ] 3 篇 ADR 架构决策记录
- [ ] ROADMAP 包含已完成项 + 后续计划 + 已知局限
- [ ] 每个技术决策附带一句话理由
