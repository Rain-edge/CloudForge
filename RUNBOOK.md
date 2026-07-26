# CloudForge 项目运行指南（踩坑版）

## 前置条件

- Docker Desktop（已启动）
- kubectl、k3d、helm 已安装
- k6 已安装

## 阶段一：Docker Compose 本地开发

### 踩过的问题
1. `docker-compose.yml` 中 `POSTGRES_PASSWORD: [redacted]` 被 YAML 解析为数组 → 改成 `"cloudforge"`
2. Dockerfile Alpine 版在国内网络下编译 C 扩展（asyncpg、bcrypt）极慢 → 改成 python:3.11-slim
3. Debian 源和 Docker Hub 拉镜像慢 → Dockerfile 加了阿里云镜像源
4. Docker Desktop 代理设置 `127.0.0.1:7890` 没开时反而报错 → 清掉代理，改用 Docker Engine 里的 registry-mirrors

### 正确步骤

```powershell
cd "C:\Users\39605\Desktop\CloudForge - 副本"

# 先确保 Docker Desktop 的代理是空的（Settings → Resources → Proxies → 清空）

# 构建并启动（第一次需要几分钟）
docker compose build --no-cache app
docker compose up -d

# 验证
curl http://localhost:8000/health
# → {"status":"ok","db":"connected"}

# Swagger 文档：浏览器打开 http://localhost:8000/docs
# Prometheus 指标：http://localhost:8000/metrics
```

---

## 阶段二：Kubernetes 部署

### 踩过的问题
1. k3d 拉 ghcr.io 镜像被墙 → 开梯子全局模式 + Docker Desktop 配代理 `127.0.0.1:7890`
2. kube-prometheus-stack 新版 chart 不接受数字 `labelValue=1` → 改用 `--set-string`
3. Helm chart 模板 bug：`{{ $value }}` 未定义变量、`readOnlyRootFilesystem` 字段不被 k3s 支持 → 修了 prometheusrule.yaml 和 deployment.yaml
4. Bitnami 子 chart 镜像（postgresql、redis）拉不下来 → **跳过 Bitnami，手写 K8s 原生 Deployment**
5. 本地镜像 `cloudforge--app:latest` 和 `postgres:14-alpine` 没导入 k3d → `k3d image import`
6. `imagePullPolicy: Never` 导致 postgres 找不到 → 改回 `IfNotPresent`

### 正确步骤

```powershell
cd "C:\Users\39605\Desktop\CloudForge - 副本"

# 1. 创建 k3d 集群（需要开梯子全局模式 + Docker 代理 127.0.0.1:7890）
k3d cluster create cloudforge --servers 1 --agents 2 -p "80:80@loadbalancer" -p "443:443@loadbalancer" --wait

# 关梯子，清空 Docker 代理（Settings → Resources → Proxies → 清空）

# 2. 导入本地镜像到 k3d
k3d image import postgres:14-alpine redis:7-alpine cloudforge--app:latest -c cloudforge

# 3. 安装可观测性栈（Prometheus + Grafana）
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

# 4. 部署 CloudForge
helm install cloudforge ./chart --wait

# 5. 验证 Pod 状态（应该全部 Running，没有 Bitnami 残留）
kubectl get pods
# 期望：cloudforge-xxx (2个副本) + cloudforge-pg-xxx + cloudforge-redis-xxx

# 6. 端口转发 + API 验证
kubectl port-forward svc/cloudforge 8000:8000
# 新终端：
curl http://localhost:8000/health
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"test","status":"pending"}'
curl http://localhost:8000/tasks
```

---

## 阶段三：可观测性验证

```powershell
# Grafana（新终端）
kubectl port-forward -n monitoring svc/monitoring-grafana 13030:80
# 浏览器打开 http://localhost:13030，用户名 admin，密码 admin
```

---

## 阶段四：k6 压测 + HPA 弹性扩缩容

```powershell
# 终端 A：观察 HPA 和 Pod 变化
kubectl get hpa cloudforge -w

# 终端 B：另开一个窗口观察 Pod 数量
kubectl get pods -w

# 终端 C：跑压测（需要先 port-forward 8000）
k6 run scripts/load-test.js -e BASE_URL=http://localhost:8000

# 观察结果：
# - CPU 会从 4% 飙升到 200%+，触发 HPA 扩容
# - 副本数从 2 自动增长到 4 → 6
# - 压测结束后几分钟，CPU 降回 4%，副本慢慢缩回 2 个
```

---

## 阶段五：清理

```powershell
# 停掉 K8s 集群
k3d cluster stop cloudforge

# 删掉 K8s 集群（彻底清理）
k3d cluster delete cloudforge

# 停掉 Docker Compose
docker compose down -v
```
