# CloudForge Roadmap

## ✅ Completed

- [x] FastAPI CRUD 微服务（Task Manager）
- [x] pytest 测试套件（10 tests, 0 warnings）
- [x] Docker 多阶段构建（builder → alpine runtime, < 100MB）
- [x] Docker Compose 本地开发环境
- [x] Helm Chart（Deployment, Service, Ingress, HPA, PDB, ConfigMap, Secret）
- [x] GitHub Actions CI（test → build-push multi-arch → manifest）
- [x] ArgoCD Application（GitOps 自动同步）
- [x] Ingress-Nginx Canary 流量切分配置
- [x] OpenTelemetry 自动埋点（FastAPI + SQLAlchemy → OTLP）
- [x] Prometheus metrics（/metrics endpoint, ServiceMonitor）
- [x] Grafana Dashboards（应用 + K8s）
- [x] PrometheusRule 告警规则（高错误率、高延迟、Pod 重启）
- [x] Alertmanager 配置（Webhook 接收器）
- [x] k6 压测脚本
- [x] k3d 集群创建脚本
- [x] 可观测性栈安装脚本

## 🔮 Future

- [ ] Terraform 管理云资源（AWS EKS / Azure AKS）
- [ ] Sealed Secrets 或 External Secrets Operator
- [ ] Argo Rollouts 替代手动 Canary 权重调整
- [ ] Celery 异步任务管道（注册邮件模拟）
- [ ] JWT 鉴权完善（refresh token, RBAC）
- [ ] NetworkPolicy + Pod Security Standards
- [ ] 多环境 values（dev/staging/prod）
- [ ] 数据库备份与恢复策略
- [ ] e2e 测试（Playwright 或 k6 browser）
- [ ] 服务网格集成（Istio / Linkerd）
- [ ] 镜像签名与 SBOM（Cosign + Syft）
- [ ] 多集群 ArgoCD

## ⚠️ Known Limitations

| 领域 | 局限 | 影响 |
|------|------|------|
| 数据库 | 单实例，无主从/备份 | 数据丢失风险 |
| 缓存 | Redis 单实例，复用 Broker | 缓存与队列相互影响 |
| 安全 | Secret 明文存储 | 密钥泄露风险 |
| 网络 | 无 NetworkPolicy | Pod 间全通，不符合零信任 |
| 发布 | Canary 手动调整权重 | 不具备自动化渐进式交付能力 |
| 认证 | 无 JWT 鉴权实现 | 所有 API 端点无认证保护 |
