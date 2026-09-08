# ADR-001: 用 k3s/k3d 代替手动二进制部署 K8s

## 状态
已接受

## 背景
最初考虑过按 "K8s the hard way" 的方式手动部署 Kubernetes（下载 kube-apiserver、kube-controller-manager、kube-scheduler、kubelet、kube-proxy、etcd，手动生成 TLS 证书）。这种方式教程很多，但配置量巨大，大部分时间花在证书链、systemd 单元文件、CNI 插件上。

## 决策
用 **k3s**（本地开发通过 **k3d** 起集群）代替手动二进制部署。

## 理由
1. **时间效率**：手动部署光证书和组件配置就要好几个小时，这些时间投到 GitOps、可观测性、弹性验证上更值
2. **生产可用**：k3s 是 CNCF sandbox 项目，边缘/IoT 场景有大量生产使用，不是玩具
3. **API 完全兼容**：k3s 通过 K8s 一致性测试，跑在 k3s 上的东西（Deployment、Service、Ingress、HPA、RBAC）在标准 K8s 上一模一样，学习价值没有损失
4. **差异本身是知识点**：k3s 默认用 SQLite 代替 etcd、内置组件更精简——理解这些差异本身就是对 K8s 架构的理解

## 权衡
- **失去**：手动搭建控制平面的细节经验（证书管理、组件间通信）
- **得到**：Helm、ArgoCD、HPA、Ingress 这些实际干活要用的东西

## 结果
- 本地用 k3d 一键起 1 server + 2 agents 集群（scripts/setup-k3d.sh）
- 集群兼容标准 kubectl 命令和 K8s API
