#!/usr/bin/env bash
# preload-images.sh — 预拉 observability 栈镜像到 k3d 集群（ghcr.io 镜像预拉）
#
# 背景：kube-prometheus-stack 等 chart 的镜像托管在 ghcr.io，
#       国内网络直连慢/不通，helm 安装时 containerd 逐个拉镜像会卡住。
#       经典解决是"开梯子 + Docker Desktop 配代理"，但更可控的做法是：
#       先在宿主机（有代理/Docker Hub 加速）把镜像拉下来，再 k3d image import
#       导入集群——containerd 本地已有镜像（imagePullPolicy=IfNotPresent），
#       安装时不再外拉，秒级完成。
#
# 用法：
#   bash scripts/preload-images.sh [cluster-name]   # 默认 cloudforge
# 前置：k3d 集群已创建；宿主机 Docker 可用（预拉镜像清单）
set -euo pipefail

CLUSTER="${1:-cloudforge}"

# 与 setup-observability.sh 保持一致的安装参数，确保渲染出的镜像清单一致
OBSERVABILITY_ARGS=(
  --namespace monitoring --create-namespace
  --set grafana.adminPassword=admin
  --set grafana.sidecar.dashboards.enabled=true
  --set grafana.sidecar.dashboards.label=grafana_dashboard
  --set-string grafana.sidecar.dashboards.labelValue=1
  --set grafana.sidecar.dashboards.searchNamespace=ALL
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
)

echo "=== 1/4 添加 Helm 仓库 ==="
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null

echo "=== 2/4 渲染 chart 提取镜像清单 ==="
# 三个 chart 的 image 字段（kube-prometheus-stack / loki-stack / tempo）
IMAGES="$(
  { helm template monitoring prometheus-community/kube-prometheus-stack "${OBSERVABILITY_ARGS[@]}"; \
    helm template loki grafana/loki-stack --namespace monitoring; \
    helm template tempo grafana/tempo --namespace monitoring; } \
  | grep -oE 'image: [^ ]+' | awk '{print $2}' | tr -d '"' | sort -u
)"
echo "共 $(echo "$IMAGES" | wc -l | tr -d ' ') 个镜像："
echo "$IMAGES"

echo "=== 3/4 宿主机 docker pull（有代理时此步走代理；拉不动的手动处理） ==="
for img in $IMAGES; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "  pulling $img"
    docker pull "$img"
  else
    echo "  已存在 $img"
  fi
done

echo "=== 4/4 导入 k3d 集群 ==="
k3d image import -c "$CLUSTER" $IMAGES

echo ""
echo "=== 完成：observability 栈镜像已预拉进集群，可直接 helm install（不会卡镜像） ==="
