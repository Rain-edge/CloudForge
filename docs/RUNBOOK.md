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
2. **asyncpg / bcrypt 编译太慢**：Alpine 镜像在国内网络下编译 C 扩展能等半小时。运行时镜像换成 python:3.11-slim 后问题消失。
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

1. **ghcr.io 拉不下来**：kube-prometheus-stack 的镜像在 ghcr.io，国内直连不行。开梯子全局模式 + Docker Desktop 配代理解决。
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

# 终端 C：压测（先 port-forward 8000）
k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000
```

观察结果：CPU 从 4% 飙到 200%+，HPA 触发扩容，副本 2 → 4 → 6；压测结束后几分钟 CPU 回落，副本慢慢缩回 2。

## 清理

```powershell
k3d cluster stop cloudforge
k3d cluster delete cloudforge
docker compose down -v
```
