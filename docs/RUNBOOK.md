# CloudForge 部署与排障记录

部署 CloudForge 时实际碰到的问题和最终能跑通的步骤。按阶段记录，照着做基本能完整复现。

## 本地开发：Docker Compose

启动前先确认 Docker Desktop 的代理是空的（Settings → Resources → Proxies 清空），不然后面各种连不上。

```powershell
# 在项目根目录执行
docker compose build --no-cache app
docker compose up -d

curl http://localhost:8000/health   # {"status":"ok","db":"connected"}
```

碰到的问题：

1. **POSTGRES_PASSWORD 报错**：compose 里写 `POSTGRES_PASSWORD: cloudforge` 会被 YAML 当成数组解析，启动直接失败。加引号 `"cloudforge"` 解决。
2. **asyncpg / bcrypt 编译太慢**：Alpine 镜像在国内网络下编译 C 扩展能等半小时。现在改多阶段构建（docker/Dockerfile）：编译只在 builder 阶段发生，runtime 直接复制编译产物，运行镜像体积和启动不受影响；asyncpg / cryptography / uvloop 等关键包已有 musllinux wheel，一般无需源码编译。若未来新增无 musllinux wheel 的依赖导致 builder 编译变慢，可把 builder 与 runtime 一起切回 python:3.11-slim（两阶段必须同一种 libc，不能混用）。
3. **拉镜像慢**：Dockerfile 里加了阿里云镜像源，Debian 源也一并换了。
4. **Docker Desktop 代理坑**：之前配了 `127.0.0.1:7890` 代理，不开梯子的时候反而报错。最后清掉代理配置，改用 Docker Engine 的 registry-mirrors。

## K8s 部署：k3d + Helm

创建集群（需要开全局代理，不然 ghcr.io 拉不下来）：

```powershell
k3d cluster create cloudforge --servers 1 --agents 2 -p "80:80@loadbalancer" -p "443:443@loadbalancer" --wait
```

创建完关梯子、清 Docker 代理。本地镜像要先导进集群，不然 Pod 一直 ImagePullBackOff：

```powershell
k3d image import postgres:14-alpine redis:7-alpine cloudforge--app:latest -c cloudforge
```

安装可观测性栈：

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
  --namespace monitoring --create-namespace `
  --set grafana.adminPassword=admin `
  --set grafana.sidecar.dashboards.enabled=true `
  --set grafana.sidecar.dashboards.label=grafana_dashboard `
  --set-string grafana.sidecar.dashboards.labelValue=1 `
  --set grafana.sidecar.dashboards.searchNamespace=ALL `
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false `
  --wait
```

部署应用并验证：

```powershell
helm install cloudforge ./chart --wait
kubectl get pods   # cloudforge + cloudforge-pg + cloudforge-redis 全部 Running
```

碰到的问题：

1. **ghcr.io 拉不下来**：kube-prometheus-stack 的镜像在 ghcr.io，国内直连不行。两种解法：开梯子全局模式 + Docker Desktop 配代理；更可控的是 `bash scripts/preload-images.sh`——先把渲染出的镜像清单 `docker pull`（走代理/加速），再 `k3d image import` 导入集群，containerd 本地已有镜像，helm 安装时不再外拉。
2. **labelValue=1 报错**：新版 kube-prometheus-stack chart 不接受纯数字的 labelValue，要加 `--set-string`。
3. **Helm 模板两个 bug**：`{{ $value }}` 引用了未定义变量；`readOnlyRootFilesystem` 字段 k3s 不支持。分别改了 prometheusrule.yaml 和 deployment.yaml。
4. **Bitnami 子 chart 拉不下来**：postgresql、redis 子 chart 的镜像在 Bitnami 仓库，国内拉不动。最后跳过 Bitnami，手写了原生 Deployment。
5. **镜像找不到**：本地构建的 `cloudforge--app:latest` 和 `postgres:14-alpine` 没导入 k3d，`k3d image import` 解决。
6. **postgres 起不来**：`imagePullPolicy: Never` 导致从本地找不到镜像，改回 `IfNotPresent` 后正常。

## 验证可观测性

```powershell
kubectl port-forward -n monitoring svc/monitoring-grafana 13030:80
# 浏览器打开 http://localhost:13030，admin / admin
```

## k6 压测 + HPA

开三个终端：

```powershell
# 终端 A：观察 HPA
kubectl get hpa cloudforge -w

# 终端 B：观察 Pod 数量
kubectl get pods -w

# 终端 C：压测（先 port-forward 8000，--summary-export 把 p95/错误率落盘留存）
k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000 --summary-export=summary.json
```

观察结果（2026-08-28 两轮实测，详见 docs/experiments/2026-08-28-k6-hpa/RESULTS.md）：
CPU 从 4% 飙到 152%～168%，HPA 触发扩容，两轮实测扩容路径分别为
2 → 3 → 5 → 6 和 2 → 4 → 5 → 6 → 7（扩容步长由 HPA 算法决定，非固定逐级）；
压测结束后 CPU 回落，副本约 6～9 分钟缩回 2（缩容稳定窗口 K8s 默认 300s）。

## 实验记录（面试数据备份）

重跑实验时照此操作并记录结果，把数据存档到仓库（截图或 summary 文件），面试被追问时能拿出证据。

### 0. 镜像体积存档（2026-08-27 实测）

```powershell
docker images | grep cloudforge
# cloudforge--app:latest   8447fa81c49e   174MB
# 对照：单阶段 python:3.11-slim 旧版 487MB（瘦身 64%）
```

### 1. k6 压测存档

```powershell
k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000 --summary-export=summary.json
```

2026-08-28 实测（summary.json 已提交到 docs/experiments/2026-08-28-k6-hpa/）：

| 指标 | 第一轮（OTel 未修复） | 第二轮（修复后） |
|------|---------------------|-----------------|
| p95 延迟 | 2.44s | 1.57s |
| 平均延迟 | 1.58s | 737ms |
| 错误率 | 4.79% | 0.00% |
| 总请求数 / RPS | 2439 / 15.5 | 3418 / 22.7 |

第一轮错误率根因：OTel 导出端点 `tempo:4317` 短名跨 namespace 解析失败（trace 导出重试风暴）。
修复后错误率归零；p95 仍未达 500ms 阈值，瓶颈定位（WSL2/k3d overlay 网络 + SQLAlchemy async 层 + 单 worker）
详见 RESULTS.md。

### 2. HPA 扩缩容过程

```powershell
kubectl get hpa cloudforge -w     # 记录 TARGETS 列变化
kubectl get pods -w               # 记录副本数变化
```

2026-08-28 实测（hpa-watch.log 全程 2s 采样已提交）：

| 时间点 | 事件 | TARGETS | 副本数 |
|--------|------|---------|--------|
| 压测开始（18:14） | CPU 飙升 | 6% → 19% → 96% | 2 |
| 超 70m 阈值（18:15:21） | 触发扩容 | 152% | 3 |
| 18:15:36 | 继续扩容 | 140% | 5 |
| 18:15:51 | 峰值 | 92% | 6 |
| 压测结束（18:16:37） | CPU 回落 | 5% | 6（保持） |
| 18:25:22 | 稳定窗口后缩容 | 4% | 2 |

第二轮（trace 修复后）：峰值 168%、扩容至 7 副本（2→4→5→6→7），约 6 分钟缩回 2。

### 3. ArgoCD 声明偏离自愈实验

历史实测（git 提交有据）：`995b787 scale to 3 replicas via GitOps` → `dccf67d rollback: scale back to 2 replicas`——通过 GitOps 把副本 2 → 3 再回 2，ArgoCD 全程自动同步，零手工 kubectl。

selfHeal 实验（2026-08-28 实测，证据 argocd-selfheal-watch.log）：

```powershell
# 故意制造声明偏离：手动把副本数改成 1（Git 里是 2）
kubectl scale deployment cloudforge -n cloudforge --replicas=1
# 观察 ArgoCD 自动恢复（selfHeal: true）
kubectl get deployment cloudforge -n cloudforge -w
```

实测结果：19:34:54 手动缩容至 1 → **19:35:00（6 秒内）ArgoCD 自动恢复为 Git 声明的 2 副本** → 19:35:05 第二个副本就绪。全程零人工干预。

历史实测（git 提交有据）：`995b787 scale to 3 replicas via GitOps` → `dccf67d rollback: scale back to 2 replicas`——通过 GitOps 把副本 2 → 3 再回 2，ArgoCD 全程自动同步。

### 4. 金丝雀秒级回滚计时

```powershell
# 计时：weight 归零前后 nginx 热更新生效耗时
helm upgrade cloudforge ./chart --set canary.weight=0
# 用 curl 连续请求，记录返回 200 的流量占比开始变化的时间
```

2026-08-28 实测（scripts/canary-rollback-test.py，证据 canary-rollback-reqs.json）：

| 步骤 | 实测 |
|------|------|
| weight=10 | canary 实收 10/100（10%） |
| weight=50 | canary 实收 48/100（48%） |
| weight=100 | canary 实收 50/50（100%） |
| 回滚 weight=100→0 | helm upgrade 1.0s；nginx 摘流 ≤2s；0 错误 |

> 前提：主 Service selector 精确匹配（component: stable）。否则 canary Pod 混入主 Service，分流失真。
> 计数方法：看 nginx controller 访问日志（upstream 字段区分 main/canary service），比数应用 Pod 日志准确。

### 5. 告警链路验证（2026-08-28 实测打通）

```powershell
# 0) 前置：注入 webhook 配置到 kube-prometheus-stack 的 Alertmanager（chart 的 Secret 不会被自动引用）
bash scripts/setup-alertmanager-webhook.sh

# 1) 端口转发 + 推测试告警（新版 Alertmanager ≥0.27 已移除 v1 API，用 v2）
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager 9093:9093
curl -X POST http://localhost:9093/api/v2/alerts -H 'Content-Type: application/json' -d '[
  {"labels":{"alertname":"TestAlert","severity":"warning","service":"cloudforge"}}
]'

# 2) 等 group_wait 30s 后查应用日志（注意：多副本时 webhook 均衡到任意 Pod，用 -l 查全部）
kubectl logs -l app=cloudforge --since=5m | grep alertmanager_webhook_received
```

实测：推送 HTTP 200，两个 Pod 共收到 21 条 `alertmanager_webhook_received`（含 trace_id/span_id）。
排查中踩的坑：
1. **chart 的 alertmanager Secret 不被 kube-prometheus-stack 引用**——它的 Alertmanager 只认自己生成的 Secret，需注入脚本
2. **webhookUrl 短名跨 namespace 解析失败**：Alertmanager 在 monitoring，`cloudforge:8000` 解析不到（no such host），默认值已改 FQDN
3. **`kubectl logs deploy/xxx` 只随机选一个 Pod**：多副本时查不到 webhook 记录是假象，要用 `-l` 或逐个 Pod 查
4. **Alertmanager 重试没有新日志 ≠ 没发送**：成功发送不打日志，看应用侧或 metrics（alertmanager_notifications_total）

## 清理

```powershell
k3d cluster stop cloudforge
k3d cluster delete cloudforge
docker compose down -v
```
