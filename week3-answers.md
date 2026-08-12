# 第三周任务答案

> 对应 `week3-plan.md` 中设计的每日任务、检验标准与自检问题的参考答案。
> 建议先自己动手实验，再对照本文件查漏补缺。

---

## Day 1 答案 — K8s 核心概念 + k3d

### ✅ 检验 1：Pod / Service / Deployment 三者的关系

```
Deployment（声明：我要 2 个副本）
    │ 管理（创建/重建/滚动更新）
    ▼
ReplicaSet（副本控制器：盯着实际数量，少了就补）
    │ 创建
    ▼
Pod  ──┐
Pod  ──┼── 一组相同 label 的 Pod
Pod  ──┘
        ▲
        │ 流量分发（按 label 选择后端）
Service（稳定入口：ClusterIP + DNS，负载均衡到所有 Ready Pod）
```

| 对象 | 职责 | 一句话 |
|------|------|--------|
| **Pod** | 运行单元 | 真正跑容器的"进程盒"，有生命周期（会被销毁重建） |
| **Deployment** | 声明式管理 | 你只声明"要几个副本"，它负责创建、更新、自愈 |
| **ReplicaSet** | 副本控制 | Deployment 的"手"，盯着实际数量与期望数量是否一致 |
| **Service** | 流量入口 | 给一组 Pod 一个稳定的 IP + DNS 名，自动负载均衡 |

**三者关系的一句话总结**：Deployment 管"数量和版本"，Service 管"流量入口"，Pod 是"干活的人"。**Pod 会死，Deployment 和 Service 不会**——这正是 K8s 自愈的基础。

### ✅ 检验 2：k3d 为什么能用 Docker 跑 K8s

1. **k3s**（Rancher 出品的轻量 K8s 发行版）：把 K8s 控制面组件（apiserver/scheduler/controller-manager）和 etcd 合并成**单个二进制**，还内置了容器运行时（containerd）和负载均衡器
2. **k3d** 把 k3s 再**容器化**：一个 k3d server 容器 = 完整控制面 + 一个工作节点；agent 容器 = 额外的工作节点
3. Docker 提供容器运行时和网络，所以 `docker ps` 能看到 4 个容器：1 个 server + 2 个 agent（+ 1 个 loadbalancer 入口代理）

**类比**：k3d = "K8s 的 Docker 版"；k3s = "K8s 的轻量版"；标准 K8s = "全量版"（etcd 独立、kubelet 独立、kube-proxy 独立……组件多、重）。

---

## Day 2 答案 — Helm Chart 结构与渲染

### ✅ 检验 1：`{{ include "cloudforge.fullname" . }}` 渲染成了什么

**渲染结果：`cloudforge`**

推导过程（对照 `_helpers.tpl`）：

```
cloudforge.fullname 定义：
  fullnameOverride 为空（values.yaml 默认值）
  → 返回 include "cloudforge.name"
cloudforge.name 定义：
  nameOverride 为空
  → 返回 default .Chart.Name = "cloudforge"
```

所以在集群里创建的所有资源名：

| 模板表达式 | 渲染结果 | 出现在 |
|-----------|---------|--------|
| `cloudforge.fullname` | `cloudforge` | Deployment / Service / HPA / PDB |
| `fullname + "-config"` | `cloudforge-config` | ConfigMap |
| `fullname + "-secret"` | `cloudforge-secret` | Secret |
| `fullname + "-pg"` | `cloudforge-pg` | PostgreSQL Deployment + Service |
| `fullname + "-redis"` | `cloudforge-redis` | Redis Deployment + Service |
| `fullname + "-canary"` | `cloudforge-canary` | 金丝雀 Deployment + Service |

`cloudforge.labels` 渲染为：

```yaml
helm.sh/chart: cloudforge-0.1.0
app.kubernetes.io/name: cloudforge
app.kubernetes.io/instance: cloudforge
app.kubernetes.io/version: 0.1.0
app.kubernetes.io/managed-by: Helm
```

（执行 `helm template cloudforge ./chart | grep -A 10 "labels:"` 可亲眼验证）

### ✅ 检验 2：Chart.yaml / values.yaml / templates/ 的分工

| 文件 | 角色 | 类比 |
|------|------|------|
| `Chart.yaml` | **包元数据**：chart 名称、版本、appVersion、类型 | 快递单上的"品名+规格" |
| `values.yaml` | **参数默认值**：副本数、镜像、资源、开关…… | 产品说明书（可被 `--set` / `-f` 覆盖） |
| `templates/` | **K8s 清单模板**：含 `{{ }}` 占位符 | 空白合同（填上 values 才是有效合同） |

**渲染公式**：`templates + values = 最终 YAML`

**values 覆盖优先级**（低 → 高）：
```
values.yaml 默认值 < -f 自定义文件 < --set 命令行参数（最高）
```

---

## Day 3 答案 — Deployment + Service + 探针

### ✅ 检验 1：livenessProbe vs readinessProbe

| 维度 | livenessProbe（存活） | readinessProbe（就绪） |
|------|----------------------|----------------------|
| 探测失败后果 | **kubelet 杀掉容器 → 重启**（RestartPolicy） | **从 Service 后端摘除**，不再分到流量（不重启） |
| 解决什么问题 | 应用死锁/卡死，进程活着但已不工作 | 应用启动中/依赖故障，暂时无法服务 |
| 本项目配置 | `/health`，initialDelay 10s，period 15s，failureThreshold 3 | `/health`，initialDelay 5s，period 5s，failureThreshold 3 |
| 恢复后 | 新容器重新启动 | 探针通过后**自动重新加入** Service |

**记忆**：liveness 管"要不要杀掉重来"；readiness 管"要不要给流量"。**readiness 失败 ≈ K8s 版的 depends_on**（依赖未就绪就不引流）。

### ✅ 检验 2：kubectl port-forward 的工作原理

```
本地浏览器 :8000 ──▶ kubectl 进程 ──(HTTPS)──▶ API Server ──▶ Pod:8000
     ▲                  │                       │
     └──────────────────┴── 双向 TCP 隧道 ───────┘
```

- kubectl 与 **API Server** 建立一条加密双向隧道（不是直连 Pod！）
- API Server 再把流量转发到目标 Pod 的 8000 端口
- 所以它**绕过了 Service 负载均衡**，直连单个 Pod
- 为什么只用于调试：所有流量都经过 API Server（单点瓶颈 + 无负载均衡 + 无高可用），生产流量走 Service/Ingress

### ✅ 检验 3：删除 Pod 后发生了什么

```
kubectl delete pod cloudforge-xxxx
  │
  ├─ 1. Pod 标记 Terminating（优雅退出，最多等 terminationGracePeriodSeconds=30s）
  ├─ 2. ReplicaSet 控制器发现：实际副本数 1 < 期望副本数 2
  ├─ 3. 立即创建新 Pod（不等旧 Pod 完全消失）
  ├─ 4. 调度器把新 Pod 分配到某个节点
  ├─ 5. kubelet 拉镜像（有缓存，秒级）→ 启动容器
  ├─ 6. readinessProbe 通过（/health 200）→ 加入 Service Endpoints
  └─ 7. 恢复流量 → 完成自愈
```

**为什么自动回来**：Deployment 是**声明式**的——你声明"永远保持 2 个副本"，ReplicaSet 就永远在"实际 vs 期望"之间纠偏。删一个补一个，这是 K8s 自愈的核心机制。

---

## Day 4 答案 — 配置分离 + 依赖服务 + HPA

### ✅ 检验 1：ConfigMap 和 Secret 的区别

| 维度 | ConfigMap | Secret |
|------|-----------|--------|
| 存放内容 | 非敏感配置：`CF_LOG_LEVEL=INFO`、`CF_LOG_FORMAT=json` | 敏感配置：`CF_DATABASE_URL`、`CF_REDIS_URL`、`CF_SECRET_KEY` |
| 编码 | 明文 | base64 编码（`kubectl get secret -o yaml` 看不到明文） |
| 存储方式 | 普通存储 | **内存（tmpfs）**，节点磁盘不留副本 |
| 生产实践 | 直接提交 Git 没问题 | 用 Sealed Secrets / External Secrets Operator / Vault 管理 |
| 注入方式 | 都一样：`envFrom.configMapRef` / `envFrom.secretRef` | 同上 |

**envFrom 注入链路验证**（Day 4 步骤 2 的预期输出）：

```bash
kubectl exec -it <app-pod> -- env | grep CF_
# CF_LOG_LEVEL=INFO                        ← 来自 ConfigMap
# CF_LOG_FORMAT=json                       ← 来自 ConfigMap
# CF_DATABASE_URL=postgresql+asyncpg://cloudforge:cloudforge@cloudforge-pg:5432/cloudforge  ← 来自 Secret
# CF_REDIS_URL=redis://cloudforge-redis:6379/0                                              ← 来自 Secret
# CF_SECRET_KEY=k8s-deploy-dev-key-32-chars!!                                               ← 来自 Secret
```

⚠️ 注意 Secret 里的 URL 主机名是 **`cloudforge-pg`**（Service 名），不是 localhost 也不是 postgres——这就是 K8s 内服务发现的体现。

### ✅ 检验 2：K8s 没有 depends_on，靠什么保证启动顺序

**双保险机制**：

| 层面 | 机制 | 作用 |
|------|------|------|
| K8s 侧 | **readinessProbe**（PG 用 `pg_isready`，app 用 `/health`） | 依赖未就绪 → 标记 NotReady → Service 不分流量 |
| 应用侧 | **app lifespan 内 SELECT 1 重试 10 次 × 2s** | 进程级兜底：容器照样启动，但连不上 PG 就重试，20s 后仍失败则启动失败 |

**关键理解**：K8s 的探针管的是"流量层面"，但容器启动时探针还没跑——所以**应用必须自己处理启动时依赖不可用**（重试/退避），两条腿走路。

### ✅ 检验 3：targetCPUUtilizationPercentage: 70 和压测的关系

**HPA 扩容公式**：
```
desiredReplicas = ceil(当前副本数 × 当前CPU利用率 / 目标CPU利用率)
例：2 副本 × (140% / 70%) = 4 副本
```

**压测联动全过程**：

```
k6 压测开始
  → app CPU 利用率从 4% 飙升到 200%+（CPU 利用率 = 实际使用 / requests.cpu=100m）
  → HPA 每 15s 采集一次指标（依赖 metrics-server，k3s 默认自带）
  → 计算：2 × (200/70) ≈ 5.7 → ceil → 6 副本
  → Deployment 滚动扩容到 6 副本 → CPU 分摊下降
  → 压测结束 → CPU 降回 4%
  → 缩容冷却期（5 分钟）后 → 副本慢慢缩回 2
```

**验证命令**：`kubectl top pods`（看实时 CPU）→ `kubectl get hpa cloudforge -w`（看 TARGETS 列从 4% → 200% → 回落）。

---

## Day 5 答案 — Ingress + 金丝雀

### ✅ 检验 1：完整流量路径

```
浏览器（curl cloudforge.local）
  │  DNS 解析（/etc/hosts 加 127.0.0.1 cloudforge.local）
  ▼
k3d loadbalancer（宿主机 80 端口 → 集群内 ingress controller）
  ▼
Ingress Controller（nginx/traefik：真正干活的路由器）
  │  读取 Ingress 规则：host=cloudforge.local + path=/ → cloudforge Service
  ▼
Service cloudforge（ClusterIP，按 label 选择后端）
  │  随机选一个 Ready 的 Pod（负载均衡）
  ▼
Pod（app 容器 :8000）
  │  envFrom 注入的 ConfigMap/Secret 环境变量
  ▼
PostgreSQL Service（cloudforge-pg:5432）→ PG Pod
```

**Ingress 和 Ingress Controller 的区别**：Ingress 是**规则声明**（YAML），Ingress Controller 是**真正干活的程序**（nginx-ingress/traefik）。没有 Controller，Ingress 就是一张废纸。

⚠️ 实操注意：k3s/k3d **默认自带 traefik**，而本项目 `ingress.className: nginx`。启用 ingress 前需要二选一：
- 安装 nginx ingress controller，或
- `helm upgrade cloudforge ./chart --set ingress.enabled=true --set ingress.className=traefik`
（用 `kubectl get ingressclass` 查看集群有哪些可用的 class）

### ✅ 检验 2：金丝雀发布的优势

| 维度 | 直接全量替换 | 金丝雀发布 |
|------|-------------|-----------|
| 新版本流量 | 100% 立即生效 | 先 1 个副本（约 1/3 流量） |
| 发现问题时 | 全部用户受影响 | 只有小部分用户受影响 |
| 回滚方式 | 重新部署旧版本（慢） | 删 canary Deployment（秒级） |
| 验证方式 | 无法对比 | 新老版本并行，可对比指标/日志 |

**本项目金丝雀工作方式**（手动实现）：
```
cloudforge 主 Deployment（2 副本，老版本 v1）
cloudforge-canary Deployment（1 副本，新版本 v2）
cloudforge-canary Service（selector: component=canary → 只指向新版本）
```
- 金丝雀的 Service 独立存在，通过调整入口（Ingress/端口转发）控制流量比例
- 验证 OK → 提升权重（把流量全切到 canary 或升级主 Deployment）
- 验证失败 → `kubectl delete deployment cloudforge-canary` 秒级回滚
- 生产级做法：Argo Rollouts 自动化渐进式交付（本项目已知局限）

### ✅ 检验 3：helm 生命周期闭环

```bash
# 安装（--wait 等所有资源就绪）
helm install cloudforge ./chart --wait

# 验证
kubectl get pods                      # 2 app + 1 pg + 1 redis
kubectl port-forward svc/cloudforge 8000:8000
curl http://localhost:8000/health     # → {"status":"ok","db":"connected"}

# 升级（滚动更新：新 Pod 就绪后老 Pod 才下线）
helm upgrade cloudforge ./chart --set replicaCount=3

# 查看版本历史
helm history cloudforge

# 回滚到上一个版本
helm rollback cloudforge 1

# 卸载（删除所有被 chart 管理的资源）
helm uninstall cloudforge
```

---

## 周末口述自检答案

**① Deployment/Service/Pod 关系？**
> Deployment 声明期望副本数并保证自愈（版本管理），Service 提供稳定的流量入口和负载均衡，Pod 是真正运行的实例。Pod 会死，Deployment/Service 不会。

**② liveness vs readiness？**
> liveness 失败 → kubelet 杀容器重启（管"活没活"）；readiness 失败 → 从 Service 摘除不引流（管"能不能接客"）。readiness 恢复后自动重新加入。

**③ port-forward 原理？**
> kubectl 通过 HTTPS 连接 API Server，API Server 转发到目标 Pod，形成本地端口 → API Server → Pod 的双向隧道。绕过了 Service 负载均衡，只用于调试。

**④ 没有 depends_on 如何保证顺序？**
> 双保险：K8s 侧用 readinessProbe（依赖就绪才标记 Ready 并引流）；应用侧在启动时对依赖做重试（本项目 lifespan SELECT 1 重试 10 次 × 2s）。探针管流量，应用重试管进程启动。

**⑤ ConfigMap vs Secret？**
> 都是"配置注入"，通过 envFrom 挂进容器环境变量。区别：ConfigMap 放明文非敏感配置（日志级别/格式），Secret 放敏感数据（连接串/密钥，base64 + 内存存储）。生产上 Secret 要用 Sealed Secrets / External Secrets 托管。

**⑥ HPA 怎么算副本数？**
> `desiredReplicas = ceil(当前副本 × 当前利用率 / 目标利用率)`。例：2 副本、CPU 140%、目标 70% → 4 副本。指标来自 metrics-server，扩容冷却 15s，缩容冷却 5min。

---

## 整周检验清单答案

| 检验项 | 答案要点 |
|--------|---------|
| 创建 k3d 集群并导入镜像 | `bash scripts/setup-k3d.sh` → `k3d image import postgres:14-alpine redis:7-alpine cloudforge--app:latest -c cloudforge`（不导入会 ImagePullBackOff） |
| helm template 与 values 对应 | `{{ .Values.replicaCount }}` → `replicas: 2`；`--set replicaCount=5` 可覆盖；`autoscaling.enabled=false` 时整个 hpa.yaml 不渲染 |
| liveness vs readiness 后果 | liveness 失败 → 重启容器；readiness 失败 → 踢出 Service 不引流 |
| 自愈演示 | `kubectl delete pod <name>` → ReplicaSet 检测副本不足 → 自动新建 → 探针通过 → 恢复 |
| 无 depends_on 的顺序保证 | readinessProbe + 应用内 SELECT 1 重试双保险 |
| ConfigMap/Secret 分工 | ConfigMap：CF_LOG_LEVEL/CF_LOG_FORMAT；Secret：CF_DATABASE_URL/CF_REDIS_URL/CF_SECRET_KEY；都经 envFrom 注入 |
| HPA 完整演示 | `helm upgrade --set autoscaling.enabled=true` → `kubectl get hpa -w` → k6 压测 → 副本 2→4→6 → 停压测 → 缩回 2 |
| 完整流量图 | 浏览器 → DNS(cloudforge.local) → k3d LB → Ingress Controller → Service → Pod → PG/Redis Service |
| helm 闭环 | install → 验证 → upgrade(--set) → rollback → uninstall |

---

## 一句话速记表

| 问题 | 一句话答案 |
|------|-----------|
| Pod/Service/Deployment 关系 | Deployment 管数量，Service 管流量，Pod 干活；Pod 会死，前两者不会 |
| k3d 是什么 | k3s（轻量 K8s）再容器化，Docker 里跑 K8s |
| helm template 渲染 | templates + values = 最终 YAML；fullname 渲染为 cloudforge |
| liveness vs readiness | 存活失败→重启；就绪失败→不引流 |
| port-forward 原理 | kubectl → API Server → Pod 双向隧道，仅调试用 |
| 删除 Pod 后 | ReplicaSet 纠偏：实际 1 < 期望 2 → 自动新建补齐 |
| 无 depends_on 怎么办 | readinessProbe（流量层）+ 应用内重试（进程层）双保险 |
| ConfigMap vs Secret | 明文 vs base64+内存；都是 envFrom 注入 |
| HPA 怎么算 | ceil(副本 × 当前利用率/目标 70%) |
| Ingress vs Controller | Ingress 是规则，Controller 是执行者 |
| 金丝雀优势 | 小流量验证、秒级回滚、影响面小 |
| ⚠️ 项目注意点 | k3s 默认 traefik，ingress.className=nginx 需改或装 nginx |
