# 第三周实施计划：Kubernetes + Helm

> **目标**：理解 K8s 资源对象如何对应 Docker Compose 的概念，掌握 Helm 部署 + kubectl 日常操作。
> **预计总时长**：约 9 小时（工作日每天 1-1.5 小时 + 周末 2 小时）
> **前置条件**：Docker Desktop（已启动）、kubectl、k3d、helm 已安装；第二周内容已掌握

---

## 0. 学习地图：Docker Compose → Kubernetes 概念映射

第三周的核心思维模型 —— **K8s 里没有"一个文件管一个服务"，而是"一个对象管一个职责"**：

| Docker Compose 概念 | Kubernetes 对应 | 在本项目的位置 |
|---------------------|----------------|---------------|
| service（一个服务） | **Deployment**（管理副本）+ **Service**（流量入口） | `deployment.yaml` + `service.yaml` |
| container（容器） | **Pod**（最小调度单元，1 个容器 = 1 个 Pod） | Deployment 的 `template` 段 |
| `depends_on` + healthcheck | **readinessProbe** + **livenessProbe** | `deployment.yaml`、`postgres.yaml`、`redis.yaml` |
| environment（环境变量） | **ConfigMap**（明文）+ **Secret**（敏感） | `configmap.yaml` + `secret.yaml` |
| `restart: unless-stopped` | **控制器自愈**（Deployment 自动重建崩溃的 Pod） | Deployment 的 ReplicaSet 机制 |
| `ports: 8000:8000` | **Service** + `kubectl port-forward` | `service.yaml` |
| 网络（compose 网络 + 服务名 DNS） | **Service DNS**：`cloudforge-pg.default.svc.cluster.local` | `postgres.yaml` 里的 Service |
| `docker compose scale` | **HPA**（自动扩缩容）/ ReplicaSet（固定副本） | `hpa.yaml` |
| 命名卷 pgdata | **PVC/PV**（⚠️ 本项目未配置，PG 数据不持久化） | 已知局限 |

---

## Day 1（周一）— K8s 核心概念 + k3d 集群搭建

**目标**：亲手创建集群，理解 Pod / Service / Deployment 三者关系。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `scripts/setup-k3d.sh`** | 理解 k3d 是什么（Docker 里跑 K8s 的轻量发行版 k3s），脚本每一步做什么 | 15min |
| 2 | **创建 k3d 集群** | `bash scripts/setup-k3d.sh`（1 server + 2 agents，映射 80/443 端口） | 20min |
| 3 | **kubectl 基础命令** | `kubectl cluster-info`、`kubectl get nodes -o wide`、`kubectl get pods -A`、`kubectl describe node cloudforge-agent-0` | 15min |
| 4 | **观察集群架构** | `docker ps` 看 k3d 实际创建了哪些容器；理解 server=控制面+调度，agent=工作节点 | 10min |

**✅ 检验**：
- 能说出 Pod / Service / Deployment 三者的关系（Deployment 管 Pod 数量，Service 管流量分发，Pod 是运行单元）
- 能解释 k3d 为什么能"用 Docker 跑 K8s"（k3s 把 K8s 组件打包进容器）

**核心知识点**：

| 概念 | 一句话解释 | 类比 |
|------|-----------|------|
| Pod | K8s 最小调度单元，含 1+ 个容器 | 一个"运行中的进程盒" |
| Deployment | 声明"我要几个副本"，自动创建/重建 Pod | 洗衣房主管（管数量、管替换） |
| Service | 稳定的流量入口，把请求转发给一组 Pod | 前台（客户只找它，不管背后几个人） |
| ReplicaSet | Deployment 底层的副本控制器 | 主管的排班表 |
| kubelet | 每个节点上的"哨兵"，负责拉镜像、启容器、报状态 | 驻场监工 |

---

## Day 2（周二）— Helm Chart 结构与渲染原理

**目标**：理解 Helm 如何把模板 + values 渲染成 K8s 清单，掌握 `helm template` 调试法。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `chart/Chart.yaml` + `values.yaml`** | Chart.yaml 是"包元数据"（名称/版本/appVersion）；values.yaml 是"可调参数"（副本数、镜像、资源、开关） | 15min |
| 2 | **精读 `chart/templates/_helpers.tpl`** | 理解 `define`/`include` 模板函数：`cloudforge.name`、`cloudforge.fullname`、`cloudforge.labels` 是公共命名和标签 | 15min |
| 3 | **渲染看真相** | `helm template cloudforge ./chart` → 对比生成的 YAML 和模板文件，理解 `{{ .Values.replicaCount }}` 等占位符如何被替换 | 20min |
| 4 | **values 覆盖实验** | `helm template cloudforge ./chart --set replicaCount=5` → 看 replicas 变 5；`--set autoscaling.enabled=true` → 看 hpa.yaml 出现 | 10min |
| 5 | **helm lint 校验** | `helm lint ./chart` → 理解 lint 检查什么 | 5min |

**✅ 检验**：
- 能解释 `helm template` 的输出中，`{{ include "cloudforge.fullname" . }}` 最终渲染成了什么
- 能说清 `Chart.yaml`、`values.yaml`、`templates/` 三者的分工

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 模板语法 | `{{ .Values.xxx }}` 取值；`{{- if ... -}}` 条件渲染（如 hpa 默认不渲染，开启才出现）；`{{ include "xxx" . }}` 引用公共模板 |
| 条件渲染 | `values.yaml` 里 `autoscaling.enabled: false` → `hpa.yaml` 整个文件不输出；这是 Helm"一个 chart 多种环境"的秘诀 |
| `_helpers.tpl` | 下划线开头 = 不直接生成 K8s 对象，只提供可复用的命名/标签函数 |
| `helm lint` | 静态检查模板语法和 Chart 规范 |

---

## Day 3（周三）— Deployment + Service + 探针（核心！）

**目标**：把 CloudForge 真正部署进集群，亲手验证 K8s 自愈能力。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **导入本地镜像** | `k3d image import postgres:14-alpine redis:7-alpine cloudforge--app:latest -c cloudforge`（⚠️ 否则拉不到镜像 Pod 起不来） | 10min |
| 2 | **精读 `deployment.yaml`** | 逐段理解：`replicas`、`selector.matchLabels`、`template`、`envFrom`、`resources`、`livenessProbe`、`readinessProbe`、`securityContext` | 20min |
| 3 | **部署 + 观察** | `helm install cloudforge ./chart --wait` → `kubectl get pods -w` → `kubectl get all` 看全量资源 | 10min |
| 4 | **自愈实验（核心）** | `kubectl delete pod cloudforge-xxxx` → 观察 K8s 自动新建一个同名前缀的新 Pod（Deployment 保证副本数） | 10min |
| 5 | **探针实验** | `kubectl describe pod <app-pod>` 看探针状态；`kubectl exec -it <pg-pod> -- psql -U cloudforge -c "SELECT 1"` 手动验证依赖 | 10min |
| 6 | **port-forward 打通** | `kubectl port-forward svc/cloudforge 8000:8000` → 新终端 `curl http://localhost:8000/health` + CRUD 全流程 | 10min |

**✅ 检验**：
- 能解释 `livenessProbe` vs `readinessProbe` 的区别（存活失败→重启 Pod；就绪失败→踢出 Service 不引流）
- 能解释 `kubectl port-forward` 的工作原理（把本地端口通过 API Server 隧道转发到集群内 Pod）
- 删除 Pod 后发生了什么？为什么它自动回来了？

**核心知识点**：

| 概念 | 说明 |
|------|------|
| `selector.matchLabels` | Deployment 靠 label 找到自己管的 Pod；**改 label 就"找不到"自己的 Pod** |
| `envFrom` | 从 ConfigMap/Secret 批量注入环境变量（等价于 Compose 的 environment） |
| `livenessProbe` | `/health` 连续 3 次失败（15s 周期）→ kubelet 杀掉重启 Pod |
| `readinessProbe` | `/health` 失败 → Pod 标记 NotReady → Service 不把流量分给它（**这就是 K8s 版的 depends_on**） |
| 自愈 | Deployment 是声明式：你声明"要 2 个"，它永远保证 2 个，删了自动补 |
| port-forward | 本质是 `kubectl` 通过 API Server 建立的 TCP 隧道，**只用于调试，不用于生产流量** |

**排障命令速查**：
```bash
kubectl get pods -o wide          # 看状态和所在节点
kubectl describe pod <name>       # 看事件（镜像拉取失败/探针失败等）
kubectl logs <name> -f            # 看应用日志
kubectl get events --sort-by=.lastTimestamp   # 看集群事件
```

---

## Day 4（周四）— 配置分离 + 依赖服务 + HPA

**目标**：理解 ConfigMap/Secret 的注入链路、K8s 里"没有 depends_on"怎么保证顺序、HPA 扩缩容。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `configmap.yaml` + `secret.yaml`** | 对比：ConfigMap 存明文（CF_LOG_LEVEL/CF_LOG_FORMAT），Secret 存敏感（数据库连接串、密钥） | 15min |
| 2 | **验证注入链路** | `kubectl exec -it <app-pod> -- env \| grep CF_` → 看到 `CF_LOG_LEVEL=INFO`（来自 ConfigMap）、`CF_DATABASE_URL=postgresql+asyncpg://cloudforge:...@cloudforge-pg:5432/...`（来自 Secret） | 10min |
| 3 | **精读 `postgres.yaml` + `redis.yaml`** | 理解：手写 Deployment + Service（不用 Bitnami 子 chart）；`readinessProbe: exec pg_isready` 与 Compose healthcheck 的对应 | 15min |
| 4 | **数据链路验证** | 通过 app 创建 task → `kubectl exec -it <pg-pod> -- psql -U cloudforge -c "SELECT * FROM tasks;"` 看到数据 → 理解 `cloudforge-pg` 服务名 DNS 解析 | 15min |
| 5 | **依赖故障实验** | `kubectl scale deploy cloudforge-pg --replicas=0` → `curl /health` 返回 503 → 再 scale 回 1 → 自动恢复（app 的 lifespan 重试 + 探针） | 15min |
| 6 | **启用 HPA** | `helm upgrade cloudforge ./chart --set autoscaling.enabled=true` → `kubectl get hpa -w` 观察 | 10min |

**✅ 检验**：
- 能说清 ConfigMap 和 Secret 的区别与各自存放什么
- 能解释 K8s 没有 `depends_on`，靠什么保证"PG 就绪后 app 才启动"（readinessProbe + app 内 SELECT 1 重试）
- 能把 `targetCPUUtilizationPercentage: 70` 和压测联系起来（CPU 利用率 >70% → 扩容，<70% → 缩容）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| ConfigMap vs Secret | 都是"配置注入"，区别只在**敏感度**和**编码**（Secret 值 base64）；生产用 External Secrets/Sealed Secrets |
| 无 depends_on 的解法 | K8s 用 **readinessProbe**（依赖方就绪才接收流量）+ **应用内重试**（app lifespan SELECT 1 重试 10 次）双保险 |
| Service DNS | `cloudforge-pg` → `cloudforge-pg.default.svc.cluster.local`，跨命名空间要写全名 |
| HPA 原理 | 指标采集（CPU 利用率）→ 控制器计算 desiredReplicas = ceil(当前副本 × 当前利用率/目标利用率) → 调整 Deployment 副本 |
| HPA 冷却 | 默认扩容 15s 内不重复、缩容 5min 内不重复（防止抖动） |

---

## Day 5（周五）— Ingress + 金丝雀 + 综合实战

**目标**：理解流量从外部到 Pod 的完整路径，掌握金丝雀发布和 helm 升级。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `ingress.yaml`** | 理解 Ingress = 7 层路由规则（host + path → Service），需要 Ingress Controller（nginx）才能生效 | 15min |
| 2 | **精读 `deployment-canary.yaml` + `service-canary.yaml`** | 理解金丝雀原理：独立 Deployment 跑新版本，独立 Service，手动调权重分发流量 | 15min |
| 3 | **金丝雀实验** | `helm upgrade cloudforge ./chart --set canary.enabled=true --set canary.tag=canary-v2` → `kubectl get deploy,pods -l app.kubernetes.io/component=canary` | 15min |
| 4 | **回滚实验** | `helm upgrade cloudforge ./chart --set canary.enabled=false` 或 `kubectl delete deployment cloudforge-canary` → 观察回滚 | 10min |
| 5 | **从零到一完整部署** | `helm uninstall cloudforge` → 重新 `helm install cloudforge ./chart` → 完整验证（health + CRUD + metrics） | 20min |
| 6 | **看 `pdb.yaml` + `servicemonitor.yaml`** | 了解 PDB（维护时保证最少可用副本）和 ServiceMonitor（Prometheus 自动发现）的设计意图 | 10min |

**✅ 检验**：
- 能画出流量路径：`浏览器 → Ingress → Service → Pod`
- 能说出金丝雀发布相比"直接全量替换"的优势（小流量验证新版本，出问题回滚影响面小）
- 能独立完成 `helm install` → 验证 → `helm upgrade` → `helm uninstall` 闭环

**核心知识点**：

| 概念 | 说明 |
|------|------|
| Ingress | 7 层路由（HTTP），一个入口路由到多个 Service；NodePort/LoadBalancer 是 4 层 |
| Ingress Controller | 真正干活的路由器（nginx-ingress/traefik），Ingress 只是"路由规则声明" |
| 金丝雀 | 新版本 1 个副本 + 老版本 2 个副本，流量按 Service 权重分配；本项目为手动实现（生产用 Argo Rollouts 自动化） |
| PDB | PodDisruptionBudget：节点维护（drain）时保证至少 minAvailable 个 Pod 存活 |
| ServiceMonitor | Prometheus Operator 的 CRD，声明"抓谁、抓哪个端口、多久抓一次" |

---

## Day 6-7（周末）— 复盘与检验

**目标**：不看代码和文档，能画出集群全貌并独立完成部署闭环。

| 任务 | 具体操作 | 时长 |
|------|----------|------|
| **画架构图** | 画出 k3d 集群内所有对象关系：Ingress → Service → Deployment → Pod（app ×2 + pg + redis）→ ConfigMap/Secret → HPA → 探针 | 30min |
| **口述自检** | ① Deployment/Service/Pod 关系？② liveness vs readiness？③ port-forward 原理？④ 没有 depends_on 如何保证顺序？⑤ ConfigMap vs Secret？⑥ HPA 怎么算副本数？ | 15min |
| **独立跑一遍** | 删除集群重建：`k3d cluster delete cloudforge` → `bash scripts/setup-k3d.sh` → `k3d image import ...` → `helm install` → 验证 → 自愈实验 → HPA 实验 | 45min |
| **压测联动 HPA** | `kubectl port-forward svc/cloudforge 8000:8000` + `k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000` → `kubectl get hpa -w` 观察副本 2→4→6 | 30min |

**✅ 最终检验标准（LEARNING_PLAN 第三周要求）**：
- [ ] 能说清楚 Deployment、Service、Pod 三者之间的关系
- [ ] 能解释 `kubectl port-forward` 的工作原理
- [ ] 能把 HPA 的 `targetCPUUtilizationPercentage: 70` 和压测结果联系起来

---

## 常见坑点（RUNBOOK.md 阶段二踩坑记录）

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| k3d 创建失败（ghcr.io 拉不到） | k3s 镜像在 ghcr.io，国内被墙 | 开梯子全局模式 + Docker Desktop 代理 `127.0.0.1:7890`，建完集群后关掉 |
| Pod 一直 ImagePullBackOff | 本地构建的镜像没进集群 | `k3d image import cloudforge--app:latest postgres:14-alpine redis:7-alpine -c cloudforge` |
| `imagePullPolicy: Never` 导致拉不到 | 本地有镜像但 k3d 里没有 | 改回 `IfNotPresent`（或先 import 镜像） |
| Bitnami 子 chart 拉不下来 | charts.bitnami.com 国内慢 | 项目已改为手写原生 Deployment（postgres.yaml/redis.yaml） |
| helm template 报 `{{ $value }}` 未定义 | 模板变量作用域问题 | 项目已修复 prometheusrule.yaml |
| kube-prometheus-stack 的 `labelValue=1` 报错 | 新版 chart 要求字符串 | 用 `--set-string grafana.sidecar.dashboards.labelValue=1` |

---

## 整周检验清单

- [ ] 能独立创建 k3d 集群并导入本地镜像
- [ ] 能解释 `helm template` 的渲染结果与 values.yaml 的对应关系
- [ ] 能说出 livenessProbe 和 readinessProbe 失败后的不同后果
- [ ] 能完成"删除 Pod → 自动重建"的自愈演示
- [ ] 能解释 K8s 里没有 depends_on 时如何保证启动顺序
- [ ] 能说出 ConfigMap 和 Secret 的分工及注入方式
- [ ] 能完成 HPA 从启用到压测触发扩容的完整演示
- [ ] 能画出 浏览器 → Ingress → Service → Pod → PG/Redis 的完整流量图
- [ ] 能独立完成 helm install → 验证 → upgrade → uninstall 闭环
