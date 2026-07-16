#!/usr/bin/env bash
# Install observability stack on the k3d cluster
# Prerequisites: kubectl, helm, k3d cluster running

set -euo pipefail

echo "=== Installing kube-prometheus-stack (Prometheus + Grafana) ==="
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --wait

echo "=== Installing Loki + Promtail ==="
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --set promtail.enabled=true \
  --set loki.persistence.enabled=false \
  --wait

echo "=== Installing Tempo ==="
helm upgrade --install tempo grafana/tempo \
  --namespace monitoring \
  --set tempo.persistence.enabled=false \
  --wait

echo ""
echo "=== Observability stack ready ==="
echo "  Grafana:    kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80"
echo "  Prometheus: kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090"
echo "  Default Grafana credentials: admin / admin"
