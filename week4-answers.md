# 第四周任务答案

> 对应 `week4-plan.md` 中设计的每日任务、检验标准与自检问题的参考答案。
> 建议先自己动手实验（特别是 Day 4 压测联动、Day 5 触发告警），再对照本文件。

---

## Day 1 答案 — Metrics 支柱：Prometheus 指标

### ✅ 检验 1：Counter / Gauge / Histogram 的区别和适用场景

| 类型 | 特点 | 适用场景 | 项目中的例子 | 查询注意 |
|------|------|---------|-------------|---------|
| **Counter**（计数器） | 只增不减，重启归零 | 累计量：请求总数、错误总数、字节数 | `http_requests_total` | 必须用 `rate()`/`increase()` 看速率，裸查是"累计值"没意义 |
| **Gauge**（仪表） | 可增可减，反映当前值 | 当前状态：内存占用、CPU、并发连接数 | `http_requests_inprogress`（进行中请求） | 直接查当前值即可，不需要 rate() |
| **Histogram**（直方图） | 分桶累计分布 | 延迟、请求体大小等"分布"型指标 | `http_request_duration_seconds_bucket` | 用 `histogram_quantile(0.95, ...)` 算分位数 |

**一句话记忆**：
- Counter = 里程表（只往前走）
- Gauge = 油量表（当前多少）
- Histogram = 一筐苹果按大小分桶（算 p95 = 找出 95% 的苹果都小于哪个桶）

### ✅ 检验 2：为什么 `should_group_status_codes=False` 是"关键配置"

- **开启分组（默认 True）**：状态码被合并成 `2xx`、`3xx`、`4xx`、`5xx`，`http_requests_total{status="5xx"}` 能查，但**无法区分具体错误码**
- **关闭分组（本项目 False）**：保留原始值 `status="200"`、`status="404"`、`status="500"`，于是：
  - Dashboard 能写 `status=~"5.."`（正则：5 开头三位数）统计服务端错误
  - 告警规则 HighErrorRate 能写 `{status=~"5.."}` 精确圈定 5xx
  - 状态码分布图能按 200/4xx/5xx 分组展示

如果这里保持默认 True，**第四周所有的看板和告警表达式都会失效**——这就是它"关键"的原因。

### ✅ 检验 3：`http_request_duration_seconds_bucket` 是什么

它是 Histogram 类型的**累积桶**，Prometheus 文本格式长这样：

```
# HELP http_request_duration_seconds HTTP request duration histogram
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{handler="/tasks",le="0.005"} 3
http_request_duration_seconds_bucket{handler="/tasks",le="0.01"} 8
http_request_duration_seconds_bucket{handler="/tasks",le="0.025"} 15
...
http_request_duration_seconds_bucket{handler="/tasks",le="+Inf"} 42
http_request_duration_seconds_sum{handler="/tasks"} 1.83
http_request_duration_seconds_count{handler="/tasks"} 42
```

- `le="0.01"` 表示**耗时 ≤0.01 秒的请求累计 8 个**（累积语义：le 值越大计数越多）
- `le="+Inf"` = 全部请求数（42）
- `_sum` = 总耗时，`_count` = 总请求数 → `_sum/_count` = 平均延迟
- p95 计算：`histogram_quantile(0.95, sum(rate(..._bucket[1m])) by (le))` —— 找到让 95% 请求都"小于等于"的那个桶边界

### ✅ 检验 4（实验预期）：curl 打 20 次后 /metrics 的变化

```
# 打请求前：http_requests_total 只有 /health、/metrics 的探针流量
# 打 20 次 /tasks（含 404/422）后新增序列：
http_requests_total{handler="/tasks",method="GET",status="200"} 15
http_requests_total{handler="/tasks",method="POST",status="201"} 3
http_requests_total{handler="/tasks/{task_id}",method="GET",status="404"} 2
```

- **handler** 是模板化路由名（`/tasks/{task_id}` 而非真实 UUID）——`should_ignore_untemplated=True` 就是为了避免把 /metrics、/docs 这类非模板路由也统计进来产生高基数
- 每个 (method, status, handler) 组合是一个独立时间序列

---

## Day 2 答案 — Logging 支柱：structlog 结构化日志

### ✅ 检验 1：structlog processor 链每步做什么

对照 `test_logging.py` 中的配置：

```python
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,      # ① 把 contextvars 里的 request_id/trace_id/span_id 合并进本次日志事件
        structlog.processors.add_log_level,           # ② 添加 level 字段（info/warning/error）
        structlog.processors.TimeStamper(fmt="iso"),  # ③ 添加 ISO 8601 时间戳
        structlog.processors.JSONRenderer(),          # ④ 最后渲染成 JSON 字符串输出
    ],
    ...
)
```

**处理管线**（一条日志从产生到输出）：
```
logger.info("task created", task_id=...) 
  → 事件字典 {"event": "task created", "task_id": ...}
  → merge_contextvars 合并 → {"event": ..., "request_id": "xxx", "trace_id": "yyy"}
  → add_log_level → + {"level": "info"}
  → TimeStamper → + {"timestamp": "2026-07-30T10:00:00+00:00"}
  → JSONRenderer → 输出一行 JSON
```

### ✅ 检验 2：X-Request-ID 的完整旅程

```
客户端 curl -H "X-Request-ID: my-test-123"
  │
  ▼
RequestIDMiddleware.dispatch
  ├─ 1. request.headers.get("X-Request-ID") → 有则沿用，无则生成 uuid4
  ├─ 2. bind_contextvars(request_id="my-test-123")   ← 绑定到日志上下文
  ├─ 3. 提取当前 Span → bind trace_id/span_id
  ├─ 4. call_next(request) → 路由处理（此时打的所有日志都带 request_id）
  └─ 5. response.headers["X-Request-ID"] = "my-test-123"   ← 响应头回传
        ↓
客户端看到响应头 X-Request-ID: my-test-123
```

**上下游价值**：网关（Nginx/APIM）生成 ID 传给 app → app 日志带同一 ID → 响应回传 ID → 用户报障时凭 ID 一键检索全部相关日志。

### ✅ 检验 3：为什么 try/finally 必须清理 contextvars

```python
try:
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
finally:
    structlog.contextvars.unbind_contextvars("trace_id", "span_id")
```

**原因**：FastAPI/Uvicorn 用**协程池**处理请求，同一个协程会被多个请求复用。contextvars 是协程级的——如果不清理：
1. 请求 A 结束时 trace_id 还留在 contextvars 里
2. 协程被复用处理请求 B
3. 请求 B 如果没有有效 Span（或 OTel 未启动），`bind_contextvars` 不会覆盖 trace_id
4. **请求 B 的日志带上了请求 A 的 trace_id** → 日志串号，排障时两条完全无关的请求被关联在一起

`finally` 保证：即使路由抛异常（call_next 中断），清理也一定执行。

---

## Day 3 答案 — Tracing 支柱：OpenTelemetry

### ✅ 检验 1：Trace/Span 树形结构

**一次 POST /tasks 的 Span 树（Jaeger/Tempo 瀑布图）**：

```
Trace: 7f3c9a1b...（trace_id，32 位 hex）
│
├─[Span A] HTTP POST /tasks            服务: cloudforge  耗时: 45ms
│    ├─ attribute: http.status_code=201
│    ├─ attribute: http.method=POST
│    │
│    ├─[Span B] INSERT INTO tasks ...  耗时: 12ms     ← SQLAlchemyInstrumentor
│    │    └─ attribute: db.system=postgresql
│    │       attribute: db.statement=INSERT INTO tasks (id, title, ...) VALUES ...
│    │       （enable_commenter 会给 SQL 加 /*traceparent=...*/ 注释）
│    │
│    └─[Span C] SELECT ...（如果有读取）
```

- **Trace** = 整棵树（一次完整请求），全局唯一 `trace_id`
- **Span** = 树上的一个节点（一次操作），有自己的 `span_id` + 父节点的 `parent_span_id`
- 日志里的 `span_id` = 记录日志时"当前正在执行的 Span"
- 根 Span（Span A）由 FastAPIInstrumentor 创建；子 Span（SQL）由 SQLAlchemyInstrumentor 创建——**自动插桩不需要改业务代码**

### ✅ 检验 2：TracerProvider → SpanProcessor → Exporter 各自职责

```
TracerProvider（全局入口，单例）
  ├─ 持有 Resource（SERVICE_NAME=cloudforge → Tempo 里按服务名过滤）
  ├─ 创建 Tracer → 业务代码通过 tracer.start_as_current_span() 埋点
  └─ 配置了 N 个 SpanProcessor
        │
        ▼
SpanProcessor（监听每个 Span 的 start/end 事件）
  └─ BatchSpanProcessor：Span 结束先进内存队列，攒批后异步发送
        │（不阻塞业务线程；崩溃时最多丢一批）
        ▼
Exporter（把 Span 序列化发到后端）
  ├─ OTLPSpanExporter（gRPC, endpoint=tempo:4317 / localhost:4317）
  └─ ConsoleSpanExporter（兜底：打印到 stdout，本地无后端时也能看）
```

| 组件 | 类比 | 职责 |
|------|------|------|
| TracerProvider | 工厂总厂 | 创建 Tracer，绑定服务身份（Resource） |
| SpanProcessor | 车间质检员 | 处理 Span 生命周期事件；Batch 模式攒批 |
| Exporter | 物流司机 | 把 Span 运到后端（Tempo/Jaeger）或丢进 console |

### ✅ 检验 3：BatchSpanProcessor 的意义

- **不阻塞业务**：Span 结束时只入内存队列，发送是异步的；如果同步发送，网络抖动会拖慢每个请求
- **批量高效**：一次 gRPC 请求携带多个 Span，减少网络往返
- **代价**：进程崩溃时队列中未发送的 Span 会丢失（可接受的权衡；生产可加 OTLP 重试/持久化缓冲）

---

## Day 4 答案 — Grafana 看板 + PromQL 实战

### ✅ 检验 1：dashboard JSON 4 个核心字段

以 `cloudforge-overview.json` 为例：

| 字段 | 作用 | 本项目例子 |
|------|------|-----------|
| `panels[]` | 看板的面板数组，每个面板是一个对象 | 4 个面板：QPS / Error Rate / p95 / 状态码分布 |
| `gridPos` | 面板布局：`{x, y, w, h}`（x/y 起点，w/h 宽高，单位是网格） | QPS 面板 `{x:0, y:0, w:12, h:8}`（占上半屏左半） |
| `targets[].expr` | 面板的数据查询（PromQL） | `sum(rate(http_requests_total[1m])) by (method, handler)` |
| `thresholds` | 数值阈值 → 颜色（绿/黄/红） | Error Rate：>0.02 黄，>0.05 红 |

补充理解：
- `type`：面板类型（timeseries 折线 / stat 数值 / bargauge 条形）
- `templating.list`：模板变量（`${DS_PROMETHEUS}` 数据源变量，导入时选择数据源）
- `uid`：看板唯一标识（`cloudforge-overview`）

### ✅ 检验 2：手写核心 PromQL（每个部分都要能解释）

```promql
rate(http_requests_total{status="200"}[1m])
│    │                    │            │
│    │                    │            └─ 时间窗口：取最近 1 分钟的数据
│    │                    └─ 标签过滤：只统计 status="200" 的序列
│    └─ 指标名
└─ rate()：把 Counter 的累计值转成"每秒增量"（QPS）
```

**4 个核心查询（闭卷写出）**：
```promql
# 1. 总 QPS
sum(rate(http_requests_total[1m]))
# 2. 200 的 QPS
sum(rate(http_requests_total{status="200"}[1m]))
# 3. 5xx 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
# 4. p95 延迟
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

### ✅ 检验 3：压测曲线讲成完整故事

```
t=0     k6 启动，20 VU → QPS 曲线从 0 爬升
t=30s   50 VU → QPS 稳定在高位，p95 延迟开始上升
t=1m    持续高压 → CPU 利用率 >70%（利用率 = 实际 CPU / requests.cpu=100m）
t≈1m30s HPA 触发扩容：2 副本 → 4 副本 → 6 副本（副本曲线阶梯上升）
t=2m    新 Pod 就绪，流量分摊 → p95 延迟回落，QPS 继续被吃下
t=4m    k6 结束 → QPS 归零 → CPU 下降
t≈9m    缩容冷却（5min）结束 → 副本缩回 2
```

**观察点**：QPS 曲线（Metrics 应用视角）↔ 副本曲线（Metrics 集群视角）↔ CPU（联动指标）——一个压测同时驱动了 3 类面板，这就是"指标讲故事"。

---

## Day 5 答案 — 告警规则 + 三支柱串联

### ✅ 检验 1：告警完整生命周期

```
条件未满足          expr 变 true           持续 for 时长         expr 恢复 false
─────────────────  ───────────────────  ───────────────────  ─────────────────
    Inactive   ──▶    Pending     ──▶      FIRING      ──▶      Resolved
    （无告警）         （黄色：成立但           （红色：通知      （自动清除，
                      未到 for=2m）            Alertmanager）    发给 send_resolved）
```

以 HighErrorRate 为例（expr：5xx 占比 >5%，for: 2m）：
- `kubectl scale deploy cloudforge-pg --replicas=0` → /health 返回 503 → 5xx 占比飙升到 100% > 5%
- **立即**：Prometheus UI → Alerts → HighErrorRate 显示 **Pending**（条件成立，计时中）
- **2 分钟后**：仍是 Pending（for=2m 计时完成）→ **FIRING**，通知推给 Alertmanager
- `kubectl scale deploy cloudforge-pg --replicas=1` → PG 恢复 → /health 200 → 错误率归零
- 下次评估（15s 内）：expr 恢复 false → **Resolved**

**for 的作用**：防抖动。瞬时抖动（如重启瞬间的 503）不会触发告警，只有持续 2 分钟的异常才告警。

### ✅ 检验 2：Alertmanager 的 grouping / inhibition

对照 `alertmanager-config.yaml`：

| 配置 | 值 | 解决什么问题 |
|------|-----|-------------|
| `group_by: ['alertname']` | 按告警名分组 | 同一种告警（如 10 个实例都 HighErrorRate）**合并成一条通知**，防告警风暴 |
| `group_wait: 30s` | 首条通知等 30s | 攒批：30s 内同组新告警一起发，避免一条条轰炸 |
| `group_interval: 5m` | 组内新告警 5 分钟一报 | 组内出现新告警后的通知节流 |
| `repeat_interval: 1h` | 同一告警 1 小时重复一次 | 告警持续 FIRING 时，不每分钟刷屏，1h 提醒一次 |
| `inhibit_rules` | critical 抑制同 alertname 的 warning | 故障升级时（critical 已发），不再发低级别重复告警，降噪 |

**记忆**：grouping = 合并同类项防轰炸；inhibition = 高级别压住低级别。

### ✅ 检验 3：日志 trace_id → Tempo Trace 的关联原理

```
1. 请求进入 app → OTel 创建根 Span，生成 trace_id（如 7f3c9a1b...）
2. RequestIDMiddleware 从当前 Span 提取 trace_id → 注入 structlog
3. app 打日志：{"event": "...", "trace_id": "7f3c9a1b...", "span_id": "a1b2c3..."}
4. Promtail 采集 stdout → 存入 Loki（trace_id 成为日志的一个字段）
5. 同时 OTLP Exporter 把 Span 发给 Tempo（Tempo 用同样的 trace_id 索引）
6. Grafana：Loki 日志行展开 → 点击 trace_id 链接
   → Grafana 用 traceId 参数查询 Tempo → 跳转显示完整 Trace
```

**关键**：日志的 trace_id 和 Tempo 的 trace_id **同源**（都来自 OTel 当前 Span 上下文），所以能精确关联。这就是"三支柱打通"的桥梁。

### ✅ 检验 4（三支柱串联复盘——同一次 PG 故障）

| 支柱 | 你观察到的现象 | 回答了什么问题 |
|------|--------------|---------------|
| **Metrics** | Grafana Error Rate 面板从 0% 飙升到 100%；QPS 的 5xx 曲线突起 | "现在怎么样？"——服务正在大量出错 |
| **Logging** | Loki 里 `{container="cloudforge"}` 全是 503 健康检查失败 / 数据库连接错误日志 | "发生了什么？"——具体报错是连不上 PG |
| **Tracing** | Tempo 里失败的 Trace：HTTP Span 503，SQL Span 失败/缺失 | "为什么？"——链路在数据库这一环断掉 |
| **告警** | HighErrorRate Pending → 2min → FIRING → Alertmanager 通知 | "要不要叫人？"——自动通知值班 |

---

## 周末口述自检答案

**① Counter vs Histogram？**
> Counter 是只增不减的累计计数器，回答"总共多少次"，必须配 rate() 看速率；Histogram 是分桶分布采样，回答"延迟/大小如何分布"，用 histogram_quantile 算 p95/p99。选型：统计次数用 Counter，度量分布用 Histogram。

**② rate() 为什么只用于 Counter？**
> Counter 是单调递增的，rate() 计算"窗口内增量/窗口时长"得到每秒速率，语义正确。Gauge 本身可增可减，直接查当前值即可，用 rate 反而失真；Histogram 的桶也是累计的，但通常配合 rate + histogram_quantile 用。

**③ trace_id 如何贯穿日志和 Trace？**
> OTel 创建 Span 时生成 trace_id → 中间件从当前 Span 提取并注入 structlog → 日志 JSON 带 trace_id → Promtail 进 Loki；同时 Span 经 OTLP 进 Tempo，用同一 trace_id 索引。Grafana 点日志的 trace_id 即跳转 Tempo。

**④ 告警 Pending → FIRING → Resolved？**
> expr 成立 → Pending（等 for 时长防抖动）→ 持续成立 → FIRING（通知 Alertmanager）→ 条件恢复 → Resolved。for 是防瞬时抖动，repeat_interval 是防刷屏。

**⑤ 三支柱各自回答什么问题？**
> Logging：发生了什么（事件明细）；Metrics：现在怎么样（数字趋势+告警）；Tracing：为什么慢/错（单请求调用链）。桥梁是 trace_id。

---

## 整周检验清单答案速查

| 检验项 | 答案要点 |
|--------|---------|
| Counter/Gauge/Histogram | 只增累计 / 当前值 / 分布桶；rate 用于 Counter，直查用于 Gauge，quantile 用于 Histogram |
| should_group_status_codes=False | 保留原始状态码，`status=~"5.."` 过滤和告警才有效 |
| structlog processor 链 | merge_contextvars → add_log_level → TimeStamper → JSONRenderer |
| request_id/trace_id 注入链路 | 中间件读/生成 ID → bind_contextvars → 提取 OTel Span → 日志带 ID → 响应头回传 |
| Trace/Span 树 | HTTP Span（FastAPIInstrumentor）为根，SQL Span（SQLAlchemyInstrumentor）为子 |
| TracerProvider/SpanProcessor/Exporter | 工厂 / 攒批处理器 / 运输者（OTLP→Tempo，Console 兜底） |
| dashboard JSON | panels[] + gridPos + targets[].expr + thresholds |
| 4 个核心 PromQL | QPS / 200 QPS / 5xx 错误率 / p95（见上文代码块） |
| 压测联动 | QPS↑ → CPU>70% → HPA 2→4→6 → 延迟回落 → 缩回 2 |
| 告警生命周期 | Pending（for 计时）→ FIRING（通知）→ Resolved（恢复） |
| 日志→Trace 跳转 | 日志 trace_id = Tempo trace_id，同源关联 |
| 故障演练 | Metrics 看错误率 → Logs 看具体报错 → Trace 看断点 → 恢复验证 |

---

## 一句话速记表

| 问题 | 一句话答案 |
|------|-----------|
| Counter vs Gauge vs Histogram | 里程表 / 油量表 / 分桶苹果 |
| rate() 的用途 | Counter 累计值 → 每秒速率，必须配时间窗口 [1m] |
| 为什么保留原始状态码 | `status=~"5.."` 正则过滤 + 告警 expr 依赖它 |
| 日志为什么是 JSON | Loki 可索引字段，Grafana 可过滤，机器可读 |
| 为什么 finally 清理 | 协程复用 → 不清理则 trace_id 串号到下一个请求 |
| trace_id 从哪来 | OTel 当前 Span 上下文，32 位 hex |
| Span 树长什么样 | HTTP 请求为根，SQL 查询为子 |
| BatchSpanProcessor | 攒批异步发送，不阻塞业务线程 |
| 告警 for 字段 | 防抖动：条件持续 for 时长才 FIRING |
| grouping/inhibition | 合并同类防轰炸 / 高级别压低级别 |
| 日志→Trace 桥梁 | 同一个 trace_id，两端同源 |
| 三支柱各答什么 | 发生了什么 / 现在怎么样 / 为什么慢错 |
