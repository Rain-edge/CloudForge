# 第四周实施计划：可观测性三大支柱

> **目标**：理解 Logging / Metrics / Tracing 三大支柱如何协作，掌握 PromQL、Grafana 看板、告警规则与日志-Trace 关联。
> **预计总时长**：约 9.5 小时（工作日每天 1.5 小时 + 周末 2 小时）
> **前置条件**：第三周完成（k3d 集群 + CloudForge 已部署）；k6 已安装；`scripts/setup-observability.sh` 可用

---

## 0. 学习地图：可观测性三大支柱

```
                    ┌────────────────────────────────────────────┐
                    │            CloudForge 应用                  │
                    │  FastAPI + SQLAlchemy（app/ 目录）           │
                    └──────┬──────────────┬──────────────┬───────┘
                           │              │              │
              ┌────────────▼───┐  ┌───────▼────────┐  ┌──▼──────────────┐
              │   Logging      │  │    Metrics     │  │    Tracing      │
              │   structlog    │  │  Prometheus    │  │  OpenTelemetry  │
              │   JSON 日志    │  │  /metrics      │  │  OTLP/gRPC      │
              │   request_id   │  │  Counter/      │  │  span/trace     │
              │   trace_id     │  │  Histogram     │  │                 │
              └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
                      │                   │                    │
              ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
              │   Loki         │  │  Prometheus    │  │   Tempo        │
              │  (Promtail 采) │  │  (抓取)        │  │  (存储 Trace)  │
              └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
                      │                   │                    │
                      └───────────────────▼────────────────────┘
                                          │
                                  ┌───────▼────────┐
                                  │    Grafana     │
                                  │  统一可视化    │
                                  │ 日志→Trace 跳转│
                                  └────────────────┘
```

**核心思维模型**：三支柱各自回答一个问题——
- **Logging**：发生了什么？（事件记录，带上下文）
- **Metrics**：现在怎么样？（数字趋势，可告警）
- **Tracing**：为什么慢/错？（一次请求的完整调用链）

**三者的关联纽带**：`request_id` + `trace_id` 贯穿日志；`trace_id` 让日志能跳转到 Tempo 看完整调用链。

---

## Day 1（周一）— Metrics 支柱：Prometheus 指标

**目标**：理解 Prometheus 指标类型，掌握 `/metrics` 端点和 PromQL 基础。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **概念铺垫：指标类型** | 理解三种核心指标：Counter（只增不减：请求总数）、Gauge（可增可减：当前连接数）、Histogram（分布：延迟分位数） | 20min |
| 2 | **精读 `app/core/metrics.py`** | 逐行理解：`CollectorRegistry`、`Instrumentator` 的 4 个配置参数（`should_group_status_codes`、`should_ignore_untemplated`、`should_instrument_requests_inprogress`、`should_round_latency_decimals`）各自解决什么问题 | 20min |
| 3 | **看真实指标** | `curl http://localhost:8000/metrics`（本地 Compose）或 `kubectl port-forward svc/cloudforge 8000:8000` 后 curl → 找到 `http_requests_total`、`http_request_duration_seconds_bucket` 等指标 | 15min |
| 4 | **制造流量再观察** | 用 curl 打 20 次 `/tasks`（含几次 404/422）→ 再 curl /metrics → 观察 `http_requests_total` 的 status/method/handler 标签变化 | 15min |
| 5 | **理解指标暴露格式** | 对照 Prometheus 文本格式：`# HELP` / `# TYPE` 注释行 + 指标行 `metric_name{label="value"} 数值` | 10min |

**✅ 检验**：
- 能说出 Counter / Gauge / Histogram 的区别和各自适用场景
- 能解释 `should_group_status_codes=False` 为什么是"关键配置"（保留 status="200"/"404" 原值，Dashboard 才能按状态码过滤和告警）
- 能说出 `http_request_duration_seconds_bucket` 是直方图桶（le="0.1" 表示 ≤0.1s 的请求数）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 指标类型 | **Counter**：只增不减（请求数、错误数）；**Gauge**：可增可减（内存、连接数）；**Histogram**：分布（延迟桶，算 p50/p95/p99） |
| 指标命名 | `http_requests_total`（Counter 以 `_total` 结尾）、`http_request_duration_seconds`（Histogram 带 `_bucket`/`_sum`/`_count`） |
| 标签（label） | `method`、`status`、`handler` 是维度；`http_requests_total{status="200"}` 是过滤 |
| Prometheus 采集方式 | **拉模式**（scrape）：Prometheus 定期 GET 应用的 /metrics；不是应用推给 Prometheus |
| 独立 Registry | `CollectorRegistry(auto_describe=True)` 避免与系统默认 registry 冲突 |

**PromQL 入门（本周要掌握的核心 4 个查询）**：
```promql
# 1. 请求总数（当前值）
http_requests_total
# 2. 每秒请求速率（QPS）—— rate 只用于 Counter
rate(http_requests_total[1m])
# 3. 按状态码过滤的 QPS
rate(http_requests_total{status="200"}[1m])
rate(http_requests_total{status=~"5.."}[1m])
# 4. p95 延迟（histogram_quantile + 直方图桶）
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))
```

---

## Day 2（周二）— Logging 支柱：structlog 结构化日志

**目标**：理解结构化日志的价值，掌握 request_id / trace_id 注入链路。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `app/middleware/logging.py`** | 逐行理解 RequestIDMiddleware 的三件事：读/生成 `X-Request-ID` → 绑定 structlog contextvars → 提取 OTel 当前 Span 的 trace_id/span_id 注入日志 | 25min |
| 2 | **理解 contextvars 机制** | 为什么用 `bind_contextvars` / `unbind_contextvars`？try/finally 清理为什么关键（防止 trace_id "泄漏"到协程池下一个请求） | 15min |
| 3 | **看真实 JSON 日志** | `kubectl logs <app-pod>`（K8s 默认 `CF_LOG_FORMAT=json`）→ 观察每条日志的 JSON 字段：`event`、`request_id`、`trace_id`、`span_id`、`level`、`timestamp` | 15min |
| 4 | **对比 console 格式** | 本地 Compose 跑一个容器 `--env CF_LOG_FORMAT=console` 或改 `chart/values.yaml` 的 `config.logFormat` → 对比可读格式与 JSON 格式的差异 | 15min |
| 5 | **追踪一次请求的日志** | 用浏览器/curl 发一次请求（带自定义 `X-Request-ID: my-test-123`）→ 在 app 日志里 grep `my-test-123` → 观察同一请求的所有日志如何串在一起 | 10min |

**✅ 检验**：
- 能说出 structlog 的 processor 链（merge_contextvars → add_log_level → TimeStamper → JSONRenderer）每一步做什么
- 能解释 `X-Request-ID` 从请求头到响应头的完整旅程
- 能解释为什么 try/finally 中清理 contextvars 是必须的

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 结构化日志 | 日志是 JSON（机器可读），不是字符串拼接；可被 Loki 索引、Grafana 过滤 |
| contextvars | Python 协程级上下文；每个请求绑定自己的 request_id，请求结束必须清理 |
| 中间件顺序 | `app.add_middleware` 是逆序执行；RequestIDMiddleware 在 OTel 插桩之后添加，确保进入时 Span 已创建 |
| 日志-追踪关联 | 日志里带 `trace_id`（32 位 hex）+ `span_id`（16 位 hex），与 Tempo 的 Trace ID 一致 → Grafana 可跳转 |
| 格式切换 | `CF_LOG_FORMAT`：console（本地可读）/ json（K8s 采集）；ConfigMap 控制（第三周已学） |

---

## Day 3（周三）— Tracing 支柱：OpenTelemetry

**目标**：理解 Trace/Span 模型和 TracerProvider → SpanProcessor → Exporter 链路。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **概念铺垫：Trace 模型** | 理解：Trace（一次请求的完整调用链）= 多个 Span（调用链上的每一步）；每个 Span 有 trace_id、span_id、parent_span_id | 15min |
| 2 | **精读 `app/core/telemetry.py`** | 逐行理解 3 步：① 创建 TracerProvider（绑定 SERVICE_NAME）→ ② 配置 Exporter（OTLP gRPC → Tempo，失败回退 Console）→ ③ 自动插桩 FastAPI + SQLAlchemy | 25min |
| 3 | **理解自动插桩** | FastAPIInstrumentor 为每个路由自动创建 Span；SQLAlchemyInstrumentor 为每个 SQL 创建 Span（`enable_commenter` 给 SQL 加注释） | 10min |
| 4 | **本地看 Trace（Jaeger）** | `docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one` → 设 `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` 启动 app → 打几次请求 → 打开 http://localhost:16686 看 Trace 瀑布图 | 20min |
| 5 | **K8s 看 Trace（Tempo）** | `kubectl port-forward -n monitoring svc/tempo 16686:16686` → 请求几次 → Tempo UI 搜索 cloudforge 服务 → 观察 span 树（HTTP 请求 → SQL 查询） | 15min |

**✅ 检验**：
- 能画出 Trace/Span 的树形结构（一次 POST /tasks 包含哪些 Span：HTTP 请求 → 路由处理 → SQL INSERT）
- 能说出 TracerProvider → SpanProcessor → Exporter 三个组件各自职责
- 能解释 BatchSpanProcessor 的意义（批量发送，不阻塞业务线程）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| Trace | 一次请求的完整调用链（全局唯一 trace_id） |
| Span | 调用链上的一步（HTTP 调用、SQL 查询……），有开始/结束时间、属性 |
| 父子关系 | parent_span_id 把 Span 串成树；日志里的 span_id 就是当前 Span |
| 自动插桩 | 不用改业务代码，instrumentor 自动包裹框架调用生成 Span |
| Exporter | OTLP/gRPC 发送到 Tempo（K8s）；ConsoleExporter 兜底（本地无后端时打印到 stdout） |
| 服务名 | `Resource.create({SERVICE_NAME: "cloudforge"})` → Tempo 里按服务名过滤 |

**Trace 结构预期（POST /tasks）**：
```
Trace: POST /tasks
└── Span: HTTP POST /tasks            （FastAPIInstrumentor 创建）
    ├── Span: SELECT 1               （SQLAlchemy 健康检查？无，这是 get_db 的会话）
    └── Span: INSERT INTO tasks ...  （SQLAlchemyInstrumentor 创建）
        （每个 Span 有耗时，SQL 慢一眼可见）
```

---

## Day 4（周四）— Grafana 看板 + PromQL 实战 + 压测联动

**目标**：读懂 dashboard JSON 模型，亲手用 PromQL 排查真实流量。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `dashboards/cloudforge-overview.json`** | 对照结构：`panels[]`（面板数组）、`gridPos`（布局）、`targets[].expr`（PromQL 查询）、`thresholds`（阈值颜色）、`templating`（数据源变量） | 25min |
| 2 | **精读 `dashboards/cloudforge-k8s.json`** | 对比应用级 vs 集群级看板的指标来源差异：`container_cpu_usage_seconds_total`（cAdvisor）、`kube_deployment_*`（kube-state-metrics） | 15min |
| 3 | **启动可观测性栈** | `bash scripts/setup-observability.sh`（安装 kube-prometheus-stack + Loki/Promtail + Tempo）→ `kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80` | 20min |
| 4 | **导入看板 + 观察** | Grafana（admin/admin）→ Dashboards → Import 上传两个 JSON → 打开 cloudforge-overview → 当前应为空/低流量 | 10min |
| 5 | **压测联动（核心实验）** | 终端 A：`kubectl get hpa cloudforge -w`；终端 B：`kubectl port-forward svc/cloudforge 8000:8000`；终端 C：`k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000` → 同时盯着 Grafana 看板：QPS 飙升、p95 延迟上升、HPA 副本 2→4→6 | 20min |
| 6 | **Explore 手写 PromQL** | Grafana → Explore → Prometheus → 手写 `rate(http_requests_total{status="200"}[1m])` 等 4 个核心查询 | 10min |

**✅ 检验**：
- 能说出 dashboard JSON 中 4 个核心字段的作用（panels/gridPos/targets/thresholds）
- 能在 Explore 手写 `rate(http_requests_total{status="200"}[1m])` 并解释每个部分
- 能把压测曲线（QPS/延迟/副本数）讲成一个完整故事

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 看板 JSON 模型 | 整个看板是 JSON：panels 数组 + 每个 panel 的 type（timeseries/stat/bargauge）+ targets（PromQL）+ 阈值 |
| 应用级指标来源 | `/metrics`（prometheus-fastapi-instrumentator）：QPS、错误率、p95、状态码 |
| 集群级指标来源 | cAdvisor（`container_*`）+ kube-state-metrics（`kube_*`）：CPU/内存/副本/重启 |
| PromQL 核心函数 | `rate()`（Counter 变速率）、`histogram_quantile()`（直方图变分位数）、`sum() by (label)`（聚合） |
| 压测故事线 | k6 流量 → QPS 曲线上升 → CPU 利用率 >70% → HPA 扩容 → 副本曲线上升 → 延迟回落 |

**看板-代码对照表**：

| 看板面板 | PromQL | 数据来自 |
|---------|--------|---------|
| Request Rate (QPS) | `sum(rate(http_requests_total[1m])) by (method, handler)` | app /metrics |
| Error Rate | `sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))` | app /metrics |
| p95 Latency | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))` | app /metrics |
| CPU per Pod | `sum(rate(container_cpu_usage_seconds_total{container="cloudforge"}[1m])) by (pod)` | cAdvisor |
| Replica Count | `kube_deployment_spec_replicas{deployment="cloudforge"}` | kube-state-metrics |

---

## Day 5（周五）— 告警规则 + 三支柱综合验证

**目标**：读懂 PrometheusRule 和 Alertmanager 配置，完成"日志→Trace→指标"端到端演练。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **精读 `chart/templates/prometheusrule.yaml`** | 逐条理解 3 个告警：HighErrorRate（错误率>5% 持续 2min）、HighLatency（p95>1s 持续 5min）、PodRestartingFrequently；理解 `expr`/`for`/`labels`/`annotations` | 20min |
| 2 | **精读 `chart/templates/alertmanager-config.yaml`** | 理解告警路由：group_by、group_wait、group_interval、repeat_interval、receivers（webhook）、inhibit_rules（critical 抑制 warning） | 15min |
| 3 | **触发真实告警（核心实验）** | `helm upgrade cloudforge ./chart --set observability.prometheusRule.enabled=true` → 制造故障：`kubectl scale deploy cloudforge-pg --replicas=0` → 观察 Prometheus UI（9090）中 Alert 状态 Pending → 2min 后 FIRING → 恢复 PG → Alert 自动 Resolved | 25min |
| 4 | **日志→Trace 跳转** | Grafana → Explore → Loki 数据源 → 搜一条 app 日志 → 点日志里的 trace_id → 跳转 Tempo 看完整 Trace | 15min |
| 5 | **三支柱串联复盘** | 针对同一次故障（如 PG 挂掉），依次回答：Metrics 显示什么？Logs 记录什么？Trace 能看到什么？画一张三支柱联动图 | 15min |

**✅ 检验**：
- 能解释告警的完整生命周期：不触发 → Pending（expr 成立但未到 for 时长）→ FIRING（持续 for 时长）→ Resolved（恢复）
- 能说出 Alertmanager 的 grouping/inhibition 机制解决什么问题
- 能完整演示"日志行 trace_id → Tempo Trace"的跳转

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 告警规则四要素 | `expr`（触发条件 PromQL）+ `for`（持续多久才告警，防抖动）+ `labels`（severity）+ `annotations`（人类可读描述） |
| 告警生命周期 | Pending（条件成立，未到 for）→ FIRING（持续成立）→ Resolved（恢复后自动清除） |
| Alertmanager 职责 | 路由（route 树）、分组（group_by 合并同类告警防轰炸）、抑制（inhibit：critical 压住 warning）、通知（webhook/email） |
| 日志→Trace 跳转 | 日志 JSON 里的 trace_id = Tempo 的 trace ID → Grafana 数据源联动（需配置 Loki+Tempo 数据源） |
| 故障演练收益 | 用真实故障（PG 挂掉）串起三支柱，比单独学每个工具理解深 10 倍 |

---

## Day 6-7（周末）— 复盘与检验

**目标**：不看代码和文档，能用三支柱讲清楚一次完整的故障排查过程。

| 任务 | 具体操作 | 时长 |
|------|----------|------|
| **画架构图** | 画出完整链路：app（structlog/Prometheus/OTel）→ Loki/Prometheus/Tempo → Grafana（三数据源 + 日志跳 Trace）→ Alertmanager → Webhook | 30min |
| **口述自检** | ① Counter vs Histogram？② rate() 为什么只用于 Counter？③ trace_id 如何贯穿日志和 Trace？④ 告警 Pending→FIRING→Resolved？⑤ 三支柱各自回答什么问题？ | 15min |
| **独立故障演练** | 不依赖答案独立完成：制造故障（杀 PG）→ Prometheus 看到错误率上升 → 告警 FIRING → Loki 日志看 503 → Tempo 看失败 Trace → 恢复 PG → 全部恢复 | 45min |
| **手写 PromQL** | 不看笔记写出 4 个核心查询（QPS/错误率/p95/状态码），并在 Explore 验证 | 15min |
| **读 `week2-notes.md` 对照** | 项目笔记里的可观测性部分作为参考答案，对比自己的理解 | 15min |

**✅ 最终检验标准（LEARNING_PLAN 第四周要求）**：
- [ ] 能说出 Counter 和 Histogram 分别适合什么场景
- [ ] 能在 Grafana Explore 里手写 `rate(http_requests_total{status="200"}[1m])`
- [ ] 能解释日志里的 trace_id 怎么和 Tempo 里的 Trace 关联

---

## 常见坑点（RUNBOOK.md 阶段三踩坑记录 + 实操提醒）

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| kube-prometheus-stack 安装报 labelValue 错误 | 新版 chart 要求字符串值 | 用 `--set-string grafana.sidecar.dashboards.labelValue=1` |
| Grafana 端口冲突 | 3000 常被本地程序占用 | `kubectl port-forward -n monitoring svc/monitoring-grafana 13030:80`（RUNBOOK 用 13030） |
| 看板导入后是空的 | 没有流量 / 数据源变量未匹配 | 先跑 k6 压测制造流量；检查 datasource 变量选择 Prometheus |
| Tempo 看不到 Trace | app 的 `OTEL_EXPORTER_OTLP_ENDPOINT` 未指向 tempo:4317 | 确认环境变量；本地用 Jaeger 兜底（docker run jaegertracing/all-in-one） |
| 告警一直 Pending 不 FIRING | `for: 2m` 需要持续 2 分钟 | 等足时间；或临时把 for 改小测试 |
| webhook 告警没收到 | alertmanager-config 里是占位 URL（webhook.site/your-unique-id） | 替换为真实 webhook 地址，或先只看 Prometheus UI 的 Alert 状态 |
| Loki 日志没有 trace_id | 应用日志格式不是 JSON | 确认 `CF_LOG_FORMAT=json`（ConfigMap 默认已是 json） |

---

## 整周检验清单

- [ ] 能说出 Counter / Gauge / Histogram 的区别和适用场景
- [ ] 能解释 `should_group_status_codes=False` 为什么关键
- [ ] 能画出 structlog processor 链并解释每步作用
- [ ] 能解释 request_id / trace_id 从请求到日志的注入链路
- [ ] 能画出 Trace/Span 树形结构（POST /tasks → SQL 查询）
- [ ] 能说出 TracerProvider / SpanProcessor / Exporter 各自职责
- [ ] 能读懂 dashboard JSON 的 panels / targets / thresholds 结构
- [ ] 能在 Explore 手写 4 个核心 PromQL 查询
- [ ] 能演示 k6 压测 → Grafana 曲线 → HPA 扩容的联动
- [ ] 能解释告警 Pending → FIRING → Resolved 生命周期
- [ ] 能完成"日志 trace_id → Tempo Trace"跳转演示
- [ ] 能独立完成一次"故障制造 → 三支柱观察 → 恢复"演练
