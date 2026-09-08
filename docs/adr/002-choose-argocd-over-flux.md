# ADR-002: GitOps 用 ArgoCD 而不是 Flux

## 状态
已接受

## 背景
项目需要一个 GitOps 工具，让集群状态自动跟 Git 仓库同步。候选是 CNCF 毕业的两个项目：ArgoCD 和 Flux CD。

## 决策
用 **ArgoCD**。

## 理由
1. **自带 Web UI**：ArgoCD 有内置 Dashboard，能直接看应用健康状态、同步状态、资源树，排障和演示都方便
2. **单集群场景够用**：Flux 的多租户模型（Kustomize overlays、镜像自动化）对单集群项目是多余的复杂度；ArgoCD 的 Application 直接对应 Helm chart 路径，理解成本低
3. **生态更常见**：ArgoCD 在招聘要求和生产环境里出现得更多（Red Hat OpenShift GitOps 就是基于 ArgoCD 的）
4. **金丝雀扩展**：以后要做渐进式发布，可以直接接 Argo Rollouts

## 权衡
- **Flux 的优势**：它的镜像自动化控制器能在镜像仓库有新版本时自动更新镜像 tag；ArgoCD 需要显式改清单（或用 Argo CD Image Updater）
- **对本项目的处理**：CI 流水线里已有 build-push 和 manifest 步骤，镜像 tag 显式提交到 Git 反而留下清晰的审计记录，也好解释

## 结果
- ArgoCD 监听 Git 仓库的 chart/ 目录
- push 到 main 后 3 分钟内自动同步
- Web UI 通过 kubectl port-forward 访问
