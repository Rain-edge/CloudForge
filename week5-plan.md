# 第五周实施计划：CI/CD + GitOps

> **目标**：理解 CI 与 CD 的分工，掌握 GitHub Actions 流水线设计，亲手完成"代码推送 → ArgoCD 自动同步"的 GitOps 闭环，并对整个项目做最终复盘。
> **预计总时长**：约 9 小时（工作日每天 1.5 小时 + 周末 2 小时）
> **前置条件**：第四周完成；GitHub 账号 + 本地 Git 已配置；本仓库 remote 已关联 `https://github.com/Rain-edge/CloudForge.git`（master 分支，7 个提交）

---

## 0. 学习地图：CI/CD + GitOps 全流程

```
┌─────────────────────────── CI（持续集成）───────────────────────────┐
│  GitHub Actions（.github/workflows/ci.yml）                          │
│                                                                      │
│  git push main / Pull Request                                        │
│    │                                                                 │
│    ▼                                                                 │
│  [validate]     [test]          [build-push]          [create-manifest]
│  helm lint      pytest 14       docker buildx         合并 amd64+arm64
│  helm template  条用例          (linux/amd64 +        为一个 multi-arch
│  dashboard JSON                  linux/arm64 矩阵)      镜像 tag
│  校验            │                    │                    │
│    └─────────────┴────────┬───────────┴────────────────────┘
│                           ▼                                        │
│                    Docker Hub（镜像仓库）                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │ 镜像: tag（如 abc1234）
                                    ▼
┌─────────────────────────── CD（持续交付/部署）──────────────────────┐
│  ArgoCD（GitOps）—— argocd/cloudforge-app.yaml                      │
│                                                                      │
│  监听 Git 仓库（rain-edge/cloudforge, path: chart）                  │
│    │ 检测到 manifest 变化（git push 触发）                            │
│    ▼                                                                 │
│  自动 sync → 应用 Helm Chart → K8s 集群（k3d）                       │
│    │                                                                 │
│    └── 核心循环：Git 是唯一真相源（Source of Truth）                  │
│        ┌──────────┐    git push    ┌──────────┐    sync    ┌──────┐ │
│        │   Git    │ ─────────────▶ │  ArgoCD  │ ─────────▶ │  K8s │ │
│        │ (真相源) │ ◀───────────── │ (拉取比对)│ ◀───────── │ 集群 │ │
│        └──────────┘   drift 检测    └──────────┘   self-heal └──────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**一句话总览**：**CI 负责"把代码变成镜像"**（构建-测试-交付物），**CD 负责"把声明变成现实"**（manifest → 集群）；GitOps 把 CD 也变成"以 Git 为准"的声明式同步。

---

## Day 1（周一）— CI/CD 概念 + GitHub Actions 语法

**目标**：建立 CI/CD 认知框架，看懂 workflow 文件的骨架语法。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **概念：CI 和 CD 的分工** | 画对比表：CI（集成+验证+构建产物）vs CD（部署到环境）；持续交付 vs 持续部署的区别 | 15min |
| 2 | **认识 workflow 三要素** | 打开 `.github/workflows/ci.yml`，先只看骨架：`name` / `on`（触发事件）/ `jobs`（任务） | 15min |
| 3 | **理解事件触发** | `on: push: branches: [main]` + `pull_request`：什么时候跑、什么时候不跑；对比手动触发 `workflow_dispatch` | 10min |
| 4 | **理解 job 与 step** | job（独立机器）+ needs（依赖）+ steps（uses=复用 action / run=执行命令）+ matrix（矩阵并行） | 15min |
| 5 | **理解 secrets** | `${{ secrets.DOCKERHUB_USER }}`：为什么密码不能写进仓库；GitHub Settings → Secrets 配置流程 | 10min |

**✅ 检验**：
- 能说出 CI 和 CD 的分工界线（CI：代码→可发布产物；CD：产物/声明→运行环境）
- 能解释 push 和 pull_request 触发的区别（push 到 main 直接跑；PR 是合并前验证）
- 能解释 `needs: validate` 的作用（job 依赖，前一个失败后一个不跑）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| CI（持续集成） | 频繁合并代码 → 自动测试 → 自动构建 → 产出镜像/制品；失败就阻断合并 |
| CD（持续交付/部署） | 把产物/声明自动部署到环境；持续交付=部署到类生产待人工放行；持续部署=全自动 |
| 本项目分工 | GitHub Actions 是 CI（测试+构建+推镜像）；ArgoCD 是 CD（GitOps 同步到 K8s） |
| workflow | 一个 `.yml` 文件 = 一条自动化流水线 |
| action vs run | `uses: actions/checkout@v4` 复用社区现成步骤；`run: pytest ...` 执行 shell 命令 |
| matrix | 一个 job 配置多组参数并行跑（本项目 amd64/arm64 双平台构建） |

---

## Day 2（周二）— 精读 ci.yml：4 个 job 流水线

**目标**：逐行读懂本项目 CI 流水线，能画出执行 DAG 并解释每一步为什么存在。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **画流水线 DAG** | 用箭头画出 4 个 job 的依赖关系（validate → test → build-push → create-manifest），标出每步产物 | 10min |
| 2 | **精读 validate job** | 理解：安装 Helm → `helm dependency update` → `helm lint` → `helm template --debug` 冒烟 → `python3 scripts/validate-dashboards.py`（Grafana JSON 校验）；这一关"挡什么" | 20min |
| 3 | **精读 test job** | `pip install -e ".[dev]"` → `pytest app/tests -v --junitxml=results.xml` → upload-artifact 保存测试报告；`if: always()` 的作用 | 15min |
| 4 | **精读 build-push job** | 理解矩阵构建：`docker/setup-qemu-action`（模拟其他 CPU 架构）→ `setup-buildx` → `login` → `metadata-action`（生成 tag：`<sha>-amd64` / `<sha>-arm64`）→ `build-push-action` | 20min |
| 5 | **精读 create-manifest job** | `docker buildx imagetools create` 把两个架构镜像合并成 `:latest` + `:<sha>` 的 multi-arch manifest；理解"为什么合并后 pull 自动选架构" | 15min |

**✅ 检验**：
- 能画出完整 DAG：`validate → test → build-push(×2 矩阵) → create-manifest`
- 能说出 4 个 job 各自的失败保护点（validate 挡 manifest 错误、test 挡代码错误、build 挡构建错误、manifest 合并产物）
- 能解释为什么 build-push 用 `matrix.platform` 而 create-manifest 不用

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 流水线分层 | 每一层失败就阻断下游（fail fast）：语法错 → 测试挂 → 构建挂 → 不产出镜像 |
| helm template --debug | 渲染后的 YAML 不 apply，只检查模板能渲染成功（冒烟测试） |
| JUnit + upload-artifact | 测试报告结构化保存，GitHub Actions 页面可直接查看失败明细 |
| buildx + qemu | buildx 支持多架构构建；qemu 模拟非本机架构（在 amd64 上构建 arm64） |
| 镜像 tag 策略 | `type=sha,format=short` → `abc1234-amd64`；可追溯（从 tag 反查 commit） |
| imagetools create | 不重新构建，只把已有镜像引用打包成 multi-arch manifest |
| secrets | 仓库级加密变量：DOCKERHUB_USER / DOCKERHUB_TOKEN，写入 GitHub Settings → Secrets and variables |

---

## Day 3（周三）— 本地模拟 CI：把流水线在本地跑一遍

**目标**：不依赖 GitHub，在本地完整执行 CI 的每个阶段，理解"流水线 = 一串命令"的本质。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **方案选择** | 二选一：① 安装 nektos/act（在本地 Docker 里跑 GitHub Actions）；② 手动执行等价命令（推荐，更贴近理解） | 5min |
| 2 | **手动执行 validate 阶段** | `helm lint ./chart` → `helm template cloudforge ./chart > /tmp/rendered.yaml` → `python3 scripts/validate-dashboards.py` → 观察每一步输出 | 20min |
| 3 | **手动执行 test 阶段** | `pip install -e ".[dev]"` → `pytest app/tests -v`（应 14 passed）→ 验证 JUnit 报告生成 | 15min |
| 4 | **手动执行 build 阶段** | `docker build -f docker/Dockerfile -t cloudforge:ci-sim .` → `docker images` 看镜像 → 用第二周的知识解释层缓存 | 20min |
| 5 | **Git 提交流程模拟** | 创建 feature 分支 → 修改一行（如 README）→ commit → 推送到远程 → 打开 GitHub 看 Actions 是否真实触发（如果仓库有 push 权限） | 15min |

**✅ 检验**：
- 能不看笔记说出一条完整 CI 流水线由哪些命令组成（lint → template → pytest → docker build）
- 能解释"CI 本质是自动化脚本执行器"（GitHub Actions 只是托管执行环境）
- 能说清 act 工具的原理（本地 Docker 模拟 GitHub runner）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| CI 的本质 | 一串可重复执行的命令，包在流程控制里（触发条件+依赖+并行） |
| act（nektos/act） | 本地跑 GitHub Actions：`act -l` 列出 job、`act push` 模拟 push 触发 |
| 手动等价命令 | 理解 CI 无需神秘化：validate=helm lint+template；test=pytest；build=docker build |
| Git 分支模型 | feature 分支开发 → PR 合并 → main 触发 CI；保护分支 + CI 检查合并 |
| CI 的"守门"价值 | 合入 main 前所有检查通过 → main 永远是可发布状态（trunk-based） |

---

## Day 4（周四）— GitOps 概念 + ArgoCD 部署与配置

**目标**：理解 GitOps 核心思想，亲手安装 ArgoCD 并部署 CloudForge 应用。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **概念：GitOps 核心思想** | 理解三句话：Git 是唯一真相源（Source of Truth）；声明式配置（YAML 声明期望状态）；自动收敛（实际 ≠ 期望 → 自动纠正） | 15min |
| 2 | **精读 `argocd/cloudforge-app.yaml`** | 逐字段理解：`source`（repoURL/targetRevision/path）、`destination`（server/namespace）、`syncPolicy.automated`（prune/selfHeal）、`syncOptions`（CreateNamespace） | 20min |
| 3 | **安装 ArgoCD** | 确认 k3d 集群运行 → `kubectl create namespace argocd` → `kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml` → `kubectl get pods -n argocd -w` | 20min |
| 4 | **登录 ArgoCD** | 端口转发：`kubectl port-forward -n argocd svc/argocd-server 8080:443` → 获取初始密码：`kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" \| base64 -d` → 浏览器打开 https://localhost:8080（admin/初始密码） | 15min |
| 5 | **部署 CloudForge 应用** | 先手工临时修改 `argocd/cloudforge-app.yaml` 的 repoURL 指向你自己的仓库（或 fork）→ `kubectl apply -f argocd/cloudforge-app.yaml` → ArgoCD UI 观察应用状态（OutOfSync → Synced） | 20min |

**✅ 检验**：
- 能解释 GitOps 三要素（唯一真相源 / 声明式 / 自动收敛）
- 能说出 `selfHeal` 和 `prune` 各自的含义（集群漂移自动纠正 / 删除 Git 中已不存在的资源）
- 能解释 ArgoCD 的 sync 流程（拉取 Git → 渲染 manifest → 与集群 diff → apply）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| GitOps 定义 | 以 Git 仓库为唯一真相源，所有变更通过 Git 提交发起，系统自动同步 |
| ArgoCD 角色 | 运行在集群内的"Git 消费者"：轮询/Webhook 监听 Git → diff → 同步 |
| sync | 手动/自动触发：把 Git 声明的状态应用到集群（kubectl apply 的自动化） |
| self-heal（自愈） | 有人手工改了集群（kubectl edit）→ ArgoCD 检测漂移 → 自动改回 Git 状态 |
| prune（修剪） | Git 中删除了某个资源 → 同步时自动从集群删除（防孤儿资源） |
| CreateNamespace | 同步前自动创建目标 namespace（cloudforge） |
| targetRevision | 监听的分支/tag（main）——改 tag 可实现环境隔离（prod=release-1.x） |

**ArgoCD 同步过程**：
```
1. ArgoCD 拉取 Git 仓库（repoURL, targetRevision=main, path=chart）
2. 渲染 Helm Chart（helm template 等价）
3. 与集群当前状态 diff
4. 有差异 → 标记 OutOfSync
5. sync → apply 变更（先建后删，滚动更新）
6. 持续监控 → 集群被手工改 → 漂移 → self-heal 纠正
```

---

## Day 5（周五）— 端到端 GitOps 演练 + 最终项目复盘

**目标**：完成"改代码 → 推送 → ArgoCD 自动同步"全流程，串联前四周全部知识做项目复盘。

| 步骤 | 任务 | 具体操作 | 时长 |
|------|------|----------|------|
| 1 | **GitOps 闭环演练** | 修改 `chart/values.yaml`（如 `replicaCount: 3` 或 `image.tag`）→ git add/commit/push → 等待 ArgoCD 检测到变化（默认 3 分钟轮询）→ UI 或 `argocd app sync` 手动触发 → `kubectl get pods` 观察滚动更新 | 25min |
| 2 | **自愈演示（核心实验）** | `kubectl scale deploy cloudforge --replicas=1`（手工偏离 Git 声明的 2）→ 观察 ArgoCD 标记 OutOfSync → self-heal 自动改回 2 → 用 `argocd app get cloudforge` 看状态变化 | 15min |
| 3 | **Prune 演示** | 在 Git 中删除一个 chart 模板（如临时删 hpa.yaml）→ push → sync → 集群中资源被自动清理 | 10min |
| 4 | **Ingress 精读（第五周文件）** | 精读 `ingress.yaml` + `ingress-canary.yaml`：host 路由、pathType、rewrite-target 注解、canary-weight 权重注解；结合第三周知识：k3s 默认 traefik vs className=nginx | 15min |
| 5 | **全项目复盘（收尾）** | 按周串联：FastAPI 应用 → 容器化 → K8s 部署 → 可观测性 → CI/CD；对照 README 的架构图逐层指认自己亲手做过的实验 | 15min |

**✅ 检验**：
- 能完整演示：git push → ArgoCD sync → 集群变化 三步闭环
- 能演示 self-heal：手工改集群 → 自动纠正回 Git 状态
- 能画出全项目端到端架构图（GitHub → Actions → Docker Hub → ArgoCD → K8s → 可观测性）

**核心知识点**：

| 概念 | 说明 |
|------|------|
| 部署即代码 | 部署变更也是代码（chart 在 Git 里），可 review、可回滚（git revert） |
| 回滚即 revert | GitOps 下回滚 = revert 一次 commit（比 kubectl rollout undo 更优雅） |
| ArgoCD 轮询 vs Webhook | 默认 3 分钟轮询 Git；配置 Webhook 可秒级触发 |
| 金丝雀 + GitOps | 本项目手动权重；生产用 Argo Rollouts（渐进式交付 + 自动分析） |
| Ingress 注解 | nginx.ingress.kubernetes.io/canary-weight=10 → 10% 流量到 canary |
| 项目完整链路 | 一次 commit 的旅程：push → CI 测试构建 → 镜像入 Docker Hub → ArgoCD 拉新 manifest → 集群滚动更新 → Grafana 观察 → 异常 → revert 回滚 |

---

## Day 6-7（周末）— 复盘与最终检验

**目标**：形成完整的项目讲述能力（面试可讲 10 分钟），独立完成全链路演练。

| 任务 | 具体操作 | 时长 |
|------|----------|------|
| **画全链路图** | 一张纸画出：GitHub Actions（4 job DAG）→ Docker Hub → ArgoCD（sync/self-heal）→ K8s（Deployment/Service/HPA/Ingress）→ 三支柱可观测性 → 告警 → 回滚路径 | 30min |
| **口述自检** | ① CI 和 CD 的分工？② GitOps 三要素？③ sync vs self-heal 区别？④ prune 干什么？⑤ 一次 commit 的完整旅程？ | 15min |
| **独立演练** | 删掉 ArgoCD 应用重建 → 重新 apply → 观察 sync；改 values → push → 自动更新；手工 scale → 自愈 | 40min |
| **面试讲述准备** | 按 STAR 框架准备 5 个可讲项目点：多架构 CI / 金丝雀 / HPA 压测 / 日志-Trace 关联 / GitOps 自愈；每个点能讲 2 分钟 | 30min |
| **对照 README 检查** | 逐条核对 README 中"已知局限与改进方向"，确认自己理解每个局限的含义和解决方案 | 15min |

**✅ 最终检验标准（LEARNING_PLAN 第五周要求）**：
- [ ] 能说出 CI 和 CD 的分工界线
- [ ] 能解释 GitOps 的核心思想：Git 是唯一真相源
- [ ] 能说出 ArgoCD 的 sync 和 self-heal 机制

**🏆 全项目毕业检验（五周综合）**：
- [ ] 不看任何文档，从零把 CloudForge 跑起来：compose 开发 → 集群部署 → 可观测 → GitOps 同步
- [ ] 能画出完整架构图并讲清楚每个组件"为什么存在"
- [ ] 能对 README 的"已知局限"逐个说出改进方案（JWT、Sealed Secrets、Argo Rollouts、NetworkPolicy、多集群）
- [ ] 面试 5 分钟项目介绍：架构 → 亮点 → 踩坑 → 改进方向

---

## 常见坑点（GitOps 实践踩坑记录）

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| ArgoCD 安装拉镜像失败 | 镜像在 ghcr.io，国内被墙 | 开梯子全局 + Docker 代理 127.0.0.1:7890 |
| ArgoCD UI 打不开 | server 是 HTTPS + 自签证书 | `kubectl port-forward -n argocd svc/argocd-server 8080:443`，浏览器点"高级→继续访问" |
| 初始密码获取不到 | 密码存在 secret 里 | `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" \| base64 -d` |
| 应用一直 OutOfSync | selfHeal 未开 / 同步被挂起 | 确认 syncPolicy.automated.selfHeal=true；UI 手动 Sync 一次 |
| sync 报 repo 无法访问 | repoURL 写错或私有仓库未配置凭据 | 检查 repoURL 大小写（GitHub 不区分）；私有仓库在 ArgoCD 配 SSH/Token |
| apply cloudforge-app.yaml 后 namespace 不存在 | syncOptions 没配 CreateNamespace | 确认 `syncOptions: - CreateNamespace=true` |
| 镜像 tag 一直 latest | values.yaml 里 tag: latest | CI 实际推 `:<sha>`；演示用可改 `image.tag: <真实sha>` |
| act 在 Windows 跑不起来 | 需要 Docker Desktop + WSL2 | 改用"手动执行等价命令"方案（Day 3 方案二） |
| 改动后 ArgoCD 不自动同步 | 默认 3 分钟轮询 | 等一会或 UI 点 Refresh；生产配 Webhook |

---

## 整周检验清单

- [ ] 能画出 CI 流水线 DAG（validate → test → build-push → create-manifest）
- [ ] 能解释 4 个 job 各自的失败保护点
- [ ] 能在本地手动执行 CI 等价命令（helm lint → pytest → docker build）
- [ ] 能说出 GitOps 三要素（唯一真相源 / 声明式 / 自动收敛）
- [ ] 能精读 argocd/cloudforge-app.yaml 每个字段
- [ ] 能独立安装 ArgoCD 并登录 UI
- [ ] 能演示 git push → ArgoCD 自动 sync → 集群更新
- [ ] 能演示 self-heal（手工改集群自动纠正）
- [ ] 能演示 prune（Git 删除资源自动清理）
- [ ] 能解释 sync vs self-heal vs prune 的区别
- [ ] 能画出全项目端到端架构图
- [ ] 能按 STAR 框架讲 5 个项目亮点
