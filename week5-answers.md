# 第五周任务答案

> 对应 `week5-plan.md` 中设计的每日任务、检验标准与自检问题的参考答案。
> 建议先自己动手实验（尤其 Day 4 的 ArgoCD 安装、Day 5 的 self-heal 演示），再对照本文件。

---

## Day 1 答案 — CI/CD 概念 + GitHub Actions 语法

### ✅ 检验 1：CI 和 CD 的分工界线

| 维度 | CI（持续集成） | CD（持续交付/部署） |
|------|---------------|---------------------|
| 输入 | 源代码（git commit） | 构建产物（镜像）/ 声明（manifest） |
| 做什么 | 测试 + 构建 + 产出可发布物 | 把产物/声明部署到目标环境 |
| 输出 | 镜像（Docker Hub）、测试报告 | 运行中的服务（K8s 集群） |
| 失败后果 | 阻断合并（main 不可发布） | 阻断上线（环境不更新） |
| 本项目 | GitHub Actions（4 个 job） | ArgoCD（GitOps 同步） |
| 类比 | 工厂质检线（原料→合格品） | 物流配送（合格品→门店上架） |

**持续交付 vs 持续部署**：
- 持续交付（Continuous Delivery）：自动部署到类生产环境，**上线前需人工放行**（点一下按钮）
- 持续部署（Continuous Deployment）：从 commit 到生产**全自动**，无人工环节

**本项目定位**：CI 全自动（push 即构建推镜像）；CD 用 ArgoCD automated sync——`prune + selfHeal` 开启，实际上已经是**持续部署**。

### ✅ 检验 2：push 和 pull_request 触发的区别

```yaml
on:
  push:
    branches: [main]      # 推送到 main 直接跑（主干守门）
  pull_request:
    branches: [main]      # 开 PR 也跑（合并前验证）
```

| 触发事件 | 什么时候跑 | 验证什么 |
|---------|-----------|---------|
| `push` 到 main | 代码已合入主干后 | 主干永远保持可发布状态 |
| `pull_request` | PR 创建/更新/合入前 | 新代码合入前先验证（守门） |
| `workflow_dispatch` | 手动点击 | 手动触发（如补跑、发布）

**为什么两者都要**：PR 触发在**合并前**发现问题（开发者可先修）；push 触发保证**合并后**主干依然全绿（防止 PR 后其他变更破坏）。

### ✅ 检验 3：`needs: validate` 的作用

```yaml
jobs:
  validate: ...
  test:
    needs: validate      # test 必须在 validate 成功后执行
  build-push:
    needs: test          # build-push 必须在 test 成功后执行
  create-manifest:
    needs: build-push    # 最后合并 manifest
```

- `needs` 定义 job 间的**依赖关系**，形成 DAG（有向无环图）
- 前一个 job 失败 → 后一个**直接跳过不执行**（fail fast，省资源）
- 没有 needs 的 job 并行执行（本例全部串行，因为每步依赖上一步产物）

---

## Day 2 答案 — 精读 ci.yml：4 个 job 流水线

### ✅ 检验 1：流水线 DAG

```
                    ┌────────────┐
                    │  validate  │   helm lint + helm template 冒烟 + dashboard JSON 校验
                    └─────┬──────┘
                          ▼
                    ┌────────────┐
                    │    test    │   pytest 14 条用例 + JUnit 报告上传
                    └─────┬──────┘
                          ▼
              ┌───────────────────────┐
              │      build-push       │   matrix ×2 并行：
              │  ┌─────────┬─────────┐│
              │  │ amd64   │  arm64  ││   docker buildx + qemu 模拟架构
              │  └────┬────┴────┬────┘│
              └───────┼─────────┼────┘
                      ▼         ▼
              cloudforge:<sha>-amd64   cloudforge:<sha>-arm64
                      └─────┬─────┘
                            ▼
                    ┌────────────────┐
                    │ create-manifest │   imagetools create 合并 multi-arch
                    └────────┬───────┘
                             ▼
                  cloudforge:latest + cloudforge:<sha>
```

**每步产物**：
| Job | 产物 |
|-----|------|
| validate | 通过信号（无产物） |
| test | JUnit 测试报告（artifact） |
| build-push | 两个架构的镜像（Docker Hub） |
| create-manifest | multi-arch manifest tag（latest + sha） |

### ✅ 检验 2：4 个 job 各自的失败保护点

| Job | 挡住的错误 | 例子 |
|-----|-----------|------|
| **validate** | manifest/模板错误 | Helm 模板语法错、Grafana JSON 非法、values 缺字段 |
| **test** | 代码逻辑错误 | 路由 404、校验 422、指标缺失 |
| **build-push** | 构建错误 | 依赖装不上、Dockerfile 语法错、平台不支持 |
| **create-manifest** | 产物合并错误 | 两个架构镜像没推成功、tag 不存在 |

**分层价值**：错误越早发现代价越低——改一个模板错字在 validate 就拦下，比在 K8s 集群里发现省几十分钟。

### ✅ 检验 3：为什么 build-push 用 matrix 而 create-manifest 不用

- **build-push**：要构建**两个不同的东西**（amd64 和 arm64 两种架构的镜像，代码相同但机器指令集不同）→ 用 `matrix.platform` 让同一 job 按参数并行跑两次
- **create-manifest**：只是把**已存在的两个镜像引用**打包成一个索引文件（manifest），本身不区分架构 → 一个 job 跑一次即可

```yaml
# build-push：矩阵 → 并行构建两次
strategy:
  matrix:
    platform: [linux/amd64, linux/arm64]   # 2 个并行任务

# create-manifest：单任务合并
run: docker buildx imagetools create -t "${REPO}:latest" "${REPO}:${SHA}-amd64" "${REPO}:${SHA}-arm64"
```

---

## Day 3 答案 — 本地模拟 CI

### ✅ 检验 1：完整 CI 流水线的命令序列

```bash
# ── validate 阶段 ──
helm dependency update ./chart            # 拉取子 chart 依赖（本项目无依赖，可跳过）
helm lint ./chart                         # 静态检查模板
helm template cloudforge ./chart --debug  # 渲染冒烟（不 apply）
python3 scripts/validate-dashboards.py    # Grafana JSON 校验

# ── test 阶段 ──
pip install -e ".[dev]"                   # 安装依赖 + 开发工具
pytest app/tests -v                       # 14 条用例（tasks 9 + health 1 + metrics 3 + logging 1）

# ── build 阶段 ──
docker build -f docker/Dockerfile -t cloudforge:ci-sim .   # 本地构建等价镜像

# ──（可选）push 阶段 ──
docker tag cloudforge:ci-sim <user>/cloudforge:ci-sim
docker push <user>/cloudforge:ci-sim
```

**注意**：CI 里的 `actions/checkout`、`setup-python` 等 action 在本地等价为"已经在你电脑上"——这正是手动执行可行的原因。

### ✅ 检验 2：为什么说"CI 本质是自动化脚本执行器"

- GitHub Actions 提供的核心能力只有三样：**触发器**（什么时候跑）、**执行环境**（干净的 Linux 机器）、**编排**（依赖/并行/缓存/日志）
- 真正的"逻辑"全部是 `run:` 里的 shell 命令（helm、pytest、docker 都是外部工具）
- **证明**：你在本地手动敲一遍这些命令 = 跑了一遍 CI（除了环境隔离和 secrets）

**意义**：理解了这点，任何 CI 平台（Jenkins/GitLab CI/Azure DevOps）都是"换一个语法壳"，底层逻辑完全通用。

### ✅ 检验 3：act 工具的原理

```
GitHub Actions 服务器                   本地（act）
┌─────────────────────────┐            ┌──────────────────────────┐
│ workflow.yml → runner   │    类似    │ workflow.yml → act 解析  │
│ runner 拉镜像 → 跑步骤  │  ───────▶  │ 拉 Docker 镜像（node等） │
│ 步骤里是 shell 命令     │            │ 在容器里执行同一批命令   │
└─────────────────────────┘            └──────────────────────────┘
```

- act（nektos/act）读取 `.github/workflows/*.yml`，在**本地 Docker 容器**里模拟 GitHub runner 执行
- `act -l` 列出所有 job；`act push` 模拟 push 触发；`act -n` dry-run 只看不跑
- 局限：容器内环境与 GitHub runner 不完全一致（如 Docker-in-Docker 需要特殊配置）→ 本项目推荐手动等价命令方案

---

## Day 4 答案 — GitOps 概念 + ArgoCD

### ✅ 检验 1：GitOps 三要素

| 要素 | 含义 | 本项目体现 |
|------|------|-----------|
| **唯一真相源**（Source of Truth） | Git 仓库是集群状态的唯一权威描述 | chart/ 目录就是"应该长什么样"的声明 |
| **声明式配置** | 用 YAML 声明期望状态，而非命令式操作步骤 | Deployment/Service/HPA 都是声明"要什么" |
| **自动收敛** | 实际状态偏离声明时，系统自动纠正 | ArgoCD self-heal |

**对比传统运维**：
```
传统（命令式）：kubectl apply 这个 → 再改那个 → 靠人记住集群是什么样
GitOps（声明式）：Git 里写"集群应该长这样" → ArgoCD 保证它长这样
```

### ✅ 检验 2：selfHeal 和 prune 的含义

| 机制 | 英文 | 作用 | 类比 |
|------|------|------|------|
| **自愈** | selfHeal | 集群被手工改动（kubectl edit/scale）→ ArgoCD 检测到**漂移（drift）** → 自动改回 Git 声明的状态 | 保安巡逻发现桌椅被搬动 → 摆回原位 |
| **修剪** | prune | Git 中删除的资源 → 同步时自动从集群删除 | 仓库清单删了某货 → 货架自动清掉 |

**对比**：
```
selfHeal 管"不该变的变了"（集群被改 → 拉回 Git 状态）
prune    管"该删的没删"（Git 已删 → 集群跟着删）

注意：prune 是双刃剑——误删 Git 中的资源会连集群一起删，生产要谨慎（可用白名单保护）
```

### ✅ 检验 3：ArgoCD 的 sync 流程

对照 `argocd/cloudforge-app.yaml`：

```yaml
spec:
  source:                                    # 真相源在哪
    repoURL: https://github.com/Rain-edge/cloudforge   # 监听哪个仓库
    targetRevision: main                     # 监听哪个分支
    path: chart                              # 监听哪个目录
  destination:                               # 部署到哪
    server: https://kubernetes.default.svc   # 本集群
    namespace: cloudforge                    # 目标 namespace
  syncPolicy:
    automated:
      prune: true                            # Git 删 → 集群删
      selfHeal: true                         # 集群漂移 → 纠正
    syncOptions:
      - CreateNamespace=true                 # 先建 namespace
```

**同步六步**：
```
1. ArgoCD 拉取 Git 仓库（repoURL + targetRevision + path）
2. 渲染 Helm Chart（等价 helm template）
3. 与集群当前资源状态 diff
4. 有差异 → 应用标记 OutOfSync
5. 执行 sync → 按依赖顺序 apply（先建 namespace/ConfigMap/Secret，再 Deployment/Service）
6. 持续监听 → 检测到漂移 → self-heal 自动纠正
```

---

## Day 5 答案 — 端到端 GitOps 演练

### ✅ 检验 1：git push → ArgoCD sync → 集群变化 三步闭环

```
① 修改（声明变化）
   vim chart/values.yaml → replicaCount: 2 → 3

② 提交并推送（真相源更新）
   git add chart/values.yaml
   git commit -m "scale to 3 replicas"
   git push origin master

③ ArgoCD 自动同步（默认 3 分钟轮询）
   检测到 repo 更新 → 重新渲染 → diff 发现 replicas 2→3
   → 自动 sync → Deployment 滚动更新（新 Pod 就绪后老 Pod 下线）
   → kubectl get pods 看到 3 个 app Pod
```

**观察点**：`kubectl get deploy cloudforge -w` 看 `AVAILABLE` 列 2→3；ArgoCD UI 应用状态 OutOfSync → Synced（绿色）。

### ✅ 检验 2：self-heal 演示预期

```
① 制造漂移（人为违反 Git 声明）
   kubectl scale deploy cloudforge --replicas=1    # Git 里声明的是 2

② ArgoCD 检测
   UI/CLI：应用变 OutOfSync（红/黄色）"1 replicas ≠ desired 2"
   原因：ReplicaSet 不会自动补副本（只有 ArgoCD 的 sync 会纠正声明）

③ self-heal 自动纠正（几秒~1 分钟内）
   ArgoCD 执行 sync → Deployment replicas 改回 2 → 新 Pod 创建
   → 应用恢复 Synced（绿色）
```

**argocd CLI 观察**：`argocd app get cloudforge` 看 `HEALTH`/`SYNC` 列变化；或 UI 的 SYNC STATUS 从 OutOfSync → Synced。

### ✅ 检验 3：全项目端到端架构图

```
开发者
  │ git push
  ▼
GitHub（CloudForge 仓库 = 唯一真相源）
  │
  ├─▶ GitHub Actions（CI）──────────────────────────────┐
  │      validate → test → build-push → create-manifest │
  │                                                      ▼
  │                                              Docker Hub（镜像）
  │                                              cloudforge:abc1234
  │
  └─▶ ArgoCD（CD，部署在 K8s 集群内）
        │ 轮询 Git → diff → sync → self-heal
        ▼
      k3d 集群（namespace: cloudforge）
        ├─ Deployment cloudforge（2 副本）+ HPA（2→10）
        ├─ Service cloudforge → Ingress（对外入口）
        ├─ Deployment cloudforge-pg（PostgreSQL）
        └─ Deployment cloudforge-redis（Redis）
        ▼
      可观测性（namespace: monitoring）
        ├─ Prometheus 抓取 /metrics → Grafana 看板 → Alertmanager 告警
        ├─ Loki（Promtail 采集 JSON 日志 → trace_id）
        └─ Tempo（OTLP 接收 Trace）
```

**一次 commit 的完整旅程**（面试 2 分钟版）：
> "我改了一行 values.yaml 推上 GitHub → Actions 先跑 validate（helm lint + 渲染冒烟）和 test（pytest）→ 通过后 buildx 矩阵构建 amd64/arm64 镜像推到 Docker Hub 并合并 multi-arch tag → ArgoCD 轮询到仓库更新 → 渲染 chart 与集群 diff → 自动 sync 触发滚动更新 → 我打开 Grafana 看 QPS/错误率确认发布正常 → 如果出问题，git revert 一次 commit，ArgoCD 自动回滚。"

---

## 周末口述自检答案

**① CI 和 CD 的分工？**
> CI 把代码变成可发布产物（测试+构建+推镜像），失败就阻断合并；CD 把产物/声明部署到环境。本项目 GitHub Actions 是 CI，ArgoCD 是 CD。

**② GitOps 三要素？**
> ① Git 是唯一真相源（集群该长什么样只有 Git 说了算）；② 声明式配置（YAML 声明期望状态而非操作步骤）；③ 自动收敛（实际偏离期望 → 自动纠正，即 self-heal）。

**③ sync vs self-heal 区别？**
> sync 是"把 Git 的新状态应用到集群"（主动/被动拉取变更，apply）；self-heal 是"集群被手工改歪后自动改回 Git 状态"（纠偏）。sync 应对"Git 变了"，self-heal 应对"集群变了"。

**④ prune 干什么？**
> 同步时删除"Git 中已不存在的资源"，防止删了 Git 文件但集群里残留孤儿资源。

**⑤ 一次 commit 的完整旅程？**
> git push → Actions validate（helm lint/template/JSON 校验）→ test（pytest 14 条）→ build-push（amd64+arm64 矩阵）→ create-manifest（合并 multi-arch tag）→ Docker Hub → ArgoCD 轮询检测 → 渲染 diff → sync → 集群滚动更新 → Grafana 可观测验证 → 异常则 revert 回滚。

---

## 整周检验清单答案速查

| 检验项 | 答案要点 |
|--------|---------|
| CI 流水线 DAG | validate → test → build-push(×2 matrix) → create-manifest |
| 4 个 job 失败保护点 | validate 挡模板错 / test 挡代码错 / build 挡构建错 / manifest 挡产物错 |
| 本地 CI 等价命令 | helm lint → helm template → pytest → docker build |
| GitOps 三要素 | 唯一真相源 / 声明式 / 自动收敛 |
| cloudforge-app.yaml 字段 | source(repoURL/targetRevision/path) + destination(namespace) + syncPolicy(prune/selfHeal/CreateNamespace) |
| ArgoCD 安装 | create namespace → apply install.yaml → port-forward 8080:443 → 取初始密码 |
| git push → 自动 sync | 改 values → commit → push → 3 分钟轮询 → 滚动更新 |
| self-heal | kubectl scale 偏离声明 → OutOfSync → 自动改回 |
| prune | Git 删资源 → 集群自动清理 |
| sync vs self-heal vs prune | 拉取应用变更 / 纠正集群漂移 / 清理已删资源 |
| 端到端架构图 | GitHub → Actions → Docker Hub → ArgoCD → K8s → 三支柱可观测 |
| STAR 讲述 | 多架构 CI / 金丝雀 / HPA 压测 / 日志-Trace 关联 / GitOps 自愈 |

---

## 一句话速记表

| 问题 | 一句话答案 |
|------|-----------|
| CI 和 CD 的分工 | CI 把代码变镜像（测试+构建），CD 把声明变现实（部署） |
| push vs PR 触发 | push 守主干、PR 守合并前，双保险 |
| needs 的作用 | job 依赖关系，前失败后不跑（fail fast） |
| 流水线 4 job | validate → test → build-push → create-manifest |
| matrix 的意义 | 同一 job 多参数并行（amd64/arm64 双架构构建） |
| imagetools create | 合并已有镜像引用，不重新构建 |
| CI 的本质 | 一串可重复执行的 shell 命令 + 触发/环境/编排 |
| GitOps 三要素 | 唯一真相源 / 声明式 / 自动收敛 |
| sync | 把 Git 状态 apply 到集群 |
| self-heal | 集群漂移自动纠正回 Git 状态 |
| prune | Git 删了的资源集群跟着删 |
| CreateNamespace | 同步前自动建 namespace |
| 回滚方式 | git revert 一次 commit，ArgoCD 自动同步 |
| 一次 commit 旅程 | push → 测试构建 → 镜像 → ArgoCD 同步 → 集群更新 → 可观测验证 |
