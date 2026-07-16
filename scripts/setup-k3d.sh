#!/usr/bin/env bash
# CloudForge local cluster setup via k3d
# Prerequisites: Docker, kubectl, helm, k3d

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-cloudforge}"
AGENTS="${AGENTS:-2}"

echo "=== Checking prerequisites ==="
command -v docker  >/dev/null 2>&1 || { echo "Docker is required"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required"; exit 1; }
command -v helm    >/dev/null 2>&1 || { echo "helm is required"; exit 1; }
command -v k3d     >/dev/null 2>&1 || {
  echo "Installing k3d..."
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
}

echo "=== Creating k3d cluster: $CLUSTER_NAME ==="
k3d cluster create "$CLUSTER_NAME" \
  --servers 1 \
  --agents "$AGENTS" \
  -p "80:80@loadbalancer" \
  -p "443:443@loadbalancer" \
  --wait

echo "=== Cluster ready ==="
kubectl cluster-info
kubectl get nodes

echo ""
echo "=== Next steps ==="
echo "  helm install cloudforge ./chart"
echo "  kubectl port-forward svc/cloudforge 8000:8000"
