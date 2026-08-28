# 2026-08-28 实验记录（实测数据存档）

环境：Windows + WSL2 + Docker Desktop 29.7.2 + k3d（k3s v1.35.5，1 server + 2 agents）
本目录文件：`summary-run1-trace未修.json`（第一轮）、`summary.json`（第二轮）、`hpa-watch.log`（HPA 全程 2s 采样）、`pods-watch.log`、`canary-rollback-reqs.json`

## 1. pytest（21 passed）

```
21 passed in 20.67s（Python 3.11.15, pytest 9.1.1）
```

## 2. 镜像体积

```
cloudforge--app:latest  eb577d675baa  174MB
```

## 3. k6 压测两轮对比（脚本：30s 预热 20VU → 90s 主压 50VU → 30s 收尾）

| 指标 | 第一轮（OTel Trace 未修复） | 第二轮（修复后） |
|------|---------------------------|-----------------|
| p95 延迟 | 2.44s | **1.57s** |
| 平均延迟 | 1.58s | 737ms |
| 错误率 | **4.79%**（117/2439） | **0.00%**（0/3418） |
| 总请求数 | 2439 | 3418 |
| RPS | 15.5 | 22.7 |

第一轮根因：应用默认 OTel 端点 `http://tempo:4317` 在 default ns 解析不到（Tempo 在 monitoring ns），
每次请求 trace 导出失败 + 无限重试 → 延迟与错误率暴涨。修复（configmap 注入
`OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo.monitoring:4317`）后错误率归零。
阈值 p95<500ms 未达标（两轮均未达标），详见下方性能定位。

## 4. HPA 实测时间线（hpa-watch.log 全程 2s 采样）

**第一轮压测（18:14-18:17）**：
```
18:14:15 CPU 6%  → 18:14:37 19% → 18:15:05 96% → 18:15:21 152% replicas 3
→ 18:15:36 140% replicas 5 → 18:15:51 92% replicas 6 → 18:16:37 5%（保持 6）
→ 18:21:06 replicas 5 → 18:25:22 replicas 2（压测结束约 8.5 分钟后缩回 2）
```
序列：**2 → 3 → 5 → 6 → 缩回 2**（CPU 峰值 152%/70%）

**第二轮压测（18:52-18:55，trace 修复后）**：
```
18:52:08 CPU 67% → 18:52:23 168% → 18:52:38 replicas 4 → 18:52:51 132% replicas 5
→ 18:53:07 97% replicas 6 → 18:53:22 82% replicas 7（峰值 7 副本）
→ 19:00:37 replicas 5 → 19:00:52 4 → 19:01:38 2（约 6 分钟缩回）
```
序列：**2 → 4 → 5 → 6 → 7 → 缩回 2**（CPU 峰值 168%/70%）

结论：HPA 扩容路径由当时 CPU 曲线决定（desired = ceil(当前利用率/目标 × 当前副本)），
**不是固定逐级序列**。两轮实测分别为 2→3→5→6 与 2→4→5→6→7，缩容稳定窗口为 K8s 默认 300s。
触发阈值：requests.cpu=100m × targetCPU 70% = **70m**。

## 5. 性能定位（为什么 p95 未达标）

逐层实测（Pod 内，50 并发 × 100 请求）：

| 层 | 结果 |
|----|------|
| /health/live（无 DB/Redis） | avg 82ms |
| /tasks 单发 | 12-15ms |
| /tasks 50 并发 | avg 1638ms |
| PostgreSQL SELECT（单发） | 5ms |
| Redis GET | 16ms |
| 裸 asyncpg 60 并发 | avg 286ms |
| SQLAlchemy async 60 并发 | avg 987ms |

结论：**瓶颈在 SQLAlchemy async 层 + 本机 WSL2/k3d overlay 网络的并发开销**，非应用代码缺陷
（缓存/异步/连接池设计均正确：GET 走 Redis 缓存 TTL 60s 写失效、asyncpg 连接池 10+20、
pool_pre_ping、uvicorn 单 worker）。SQLAlchemy async 层在 60 并发下比裸 asyncpg 慢约 3 倍。
单 worker 事件循环在 50 VU 下接近饱和。

## 6. 金丝雀发布实测（nginx ingress 权重分流，逐请求计数）

| 权重 | canary 收到 | 比例 |
|------|------------|------|
| 10% | 10/100 | 10% ✅ |
| 50% | 48/100 | 48% ✅ |
| 100% | 50/50 | 100% ✅ |
| 回滚 100→0 | helm upgrade 1.0s，摘流 ≤2s，0 错误 | ✅ |

前置修复：主 Service selector 原为 `app=cloudforge`（会选到 canary Pod，分流失真——
实测 weight=10 时 canary 实收 33-66%）。修复：主 Deployment 加 `component: stable` 标签，
主 Service selector 精确匹配后分流精确。

## 7. 告警链路实测

- Alertmanager v2 API 推送测试告警 HTTP 200
- 应用收到 webhook：两个 Pod 共 21 条 `alertmanager_webhook_received` 结构化日志
  （含 alertname/severity/status/request_id/trace_id/span_id）
- 前置修复：
  1. chart 的 alertmanager Secret 不被 kube-prometheus-stack 引用 → `scripts/setup-alertmanager-webhook.sh` 注入
  2. webhookUrl 短名 `cloudforge:8000` 跨 namespace 解析失败（monitoring → default）→ 默认值改 FQDN
  3. Alertmanager v1 API 已移除（0.27+），验证命令用 v2 API + Content-Type: application/json

## 8. Trace 链路（OTel → Tempo）实测

修复后 Tempo 收到 cloudforge trace（23-69ms），span 结构含 HTTP + SQL 调用链，
JSON 日志携带 trace_id/span_id/request_id，Grafana 可经 Loki derivedFields 跳转 Tempo。

## 9. ArgoCD GitOps + selfHeal 实测

- 安装 argo/argo-cd（helm，NodePort 模式），应用 `argocd/cloudforge-app.yaml`（repoURL=github.com/Rain-edge/CloudForge, targetRevision=master, path=chart, selfHeal+prune）
- ArgoCD 自动同步部署到 cloudforge namespace（应用 2 副本 + PG + Redis 全部 Running，零手动 kubectl）
- **selfHeal 实测**（argocd-selfheal-watch.log）：19:34:54 `kubectl scale --replicas=1` 制造偏离 → **19:35:00（6 秒内）自动恢复为 2** → 19:35:05 就绪。零人工干预

## 10. 本轮修复清单（git commit 内容）

- `chart/templates/configmap.yaml` + `chart/values.yaml`：注入 OTEL_EXPORTER_OTLP_ENDPOINT（tempo.monitoring:4317）
- `chart/templates/deployment.yaml`：HPA 启用时不渲染 replicas（解决 helm upgrade 与 scale subresource 冲突）；主版本加 component: stable 标签
- `chart/templates/service.yaml`：selector 精确匹配 component: stable
- `chart/templates/NOTES.txt`：金丝雀回滚表述与 README 对齐（weight=0，勿 kubectl delete）
- `scripts/setup-observability.sh` / `scripts/preload-images.sh`：labelValue=1 加 --set-string（与 RUNBOOK 一致）
- `chart/values.yaml`：alertmanager.webhookUrl 默认值改 FQDN（跨 namespace）
- 新增 `scripts/setup-alertmanager-webhook.sh`（告警配置注入）、`scripts/canary-rollback-test.py`（回滚计时实验）
