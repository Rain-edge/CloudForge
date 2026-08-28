#!/usr/bin/env bash
# setup-alertmanager-webhook.sh — 把 CloudForge chart 的 Alertmanager webhook 配置
# 注入 kube-prometheus-stack 的 Alertmanager Secret，打通告警链路
#
# 背景：chart/templates/alertmanager-config.yaml 创建的 Secret
# （cloudforge-alertmanager，含 webhook receiver 配置）不会被
# kube-prometheus-stack 的 Alertmanager 引用——它只认自己生成的
# Secret alertmanager-monitoring-kube-prometheus-alertmanager。
# 本脚本把 webhook 配置写入后者，config-reloader sidecar 检测到
# Secret 变化后自动热加载，无需重启 Alertmanager。
#
# 用法：bash scripts/setup-alertmanager-webhook.sh
# 前置：cloudforge chart 已部署（Secret cloudforge-alertmanager 存在）；
#       monitoring 栈已安装
set -euo pipefail

SRC_SECRET="cloudforge-alertmanager"                      # CloudForge chart 生成的 Secret（default ns）
DST_SECRET="alertmanager-monitoring-kube-prometheus-alertmanager"  # kube-prometheus-stack 实际使用的 Secret（monitoring ns）
TMP_YAML="$LOCALAPPDATA/Temp/cloudforge-alertmanager.yaml"  # kubectl 是 Windows 原生程序，不用 MSYS /tmp

echo "=== 读取 CloudForge 的 Alertmanager 配置 ==="
kubectl get secret "$SRC_SECRET" -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d > "$TMP_YAML"
echo "--- 配置预览（前 20 行）---"
head -20 "$TMP_YAML"

echo ""
echo "=== 注入到 kube-prometheus-stack 的 Alertmanager Secret ==="
kubectl -n monitoring create secret generic "$DST_SECRET" \
  --from-file=alertmanager.yaml="$TMP_YAML" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "=== 等待 config-reloader 热加载（最多 30s） ==="
sleep 5
kubectl -n monitoring get secret "$DST_SECRET" -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d | grep -A2 'receivers' | head -6

echo ""
echo "=== 验证：向 Alertmanager 推一条测试告警 ==="
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-alertmanager 9093:9093 >/dev/null 2>&1 &
PF_PID=$!
sleep 3
curl -s -X POST http://localhost:9093/api/v2/alerts \
  -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning","service":"cloudforge"}}]' \
  -w '推送测试告警 HTTP %{http_code}\n'
kill $PF_PID 2>/dev/null || true

echo ""
echo "=== 检查应用日志是否收到 webhook（等 10s） ==="
sleep 10
kubectl logs deploy/cloudforge --since=2m 2>/dev/null | grep alertmanager_webhook_received | tail -2 || echo "未在应用日志中找到 webhook 记录（检查 webhookUrl 是否可达）"
