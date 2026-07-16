# ADR-001: Use k3s/k3d instead of manual binary K8s deployment

## Status
Accepted

## Context
The project initially considered manually deploying Kubernetes from binaries (downloading kube-apiserver, kube-controller-manager, kube-scheduler, kubelet, kube-proxy, etcd, and manually generating TLS certificates). This approach is commonly suggested in "learn K8s the hard way" guides.

## Decision
Use **k3s** (via **k3d** for local development) instead of manual binary deployment.

## Rationale
1. **Time efficiency**: Manual binary deployment requires hours of configuration and debugging (certificate chains, systemd unit files, CNI plugin setup). That time is better invested in GitOps, observability, and resilience testing — areas with higher interview differentiation.
2. **Industry relevance**: k3s is a CNCF sandbox project used in production for edge/IoT. Demonstrating familiarity with k3s is more practically useful than proving you can follow a 20-step TLS setup guide.
3. **K8s API compatibility**: k3s is fully conformant with the Kubernetes API. Everything that runs on k3s runs on standard K8s. The learning value for application-level K8s concepts (Deployments, Services, Ingress, HPA, RBAC) is identical.
4. **Demonstrates architectural understanding**: The README and ADR explain *why* k3s differs (SQLite instead of etcd by default, embedded components) — showing deeper understanding than just "I followed a tutorial."

## Tradeoffs
- **Lost**: Deep understanding of K8s control plane certificate management and component communication
- **Gained**: Practical experience with Helm, ArgoCD, HPA, Ingress controllers — skills directly applicable to any K8s role
- **Mitigation**: K8s control plane internals can be learned from "Kubernetes The Hard Way" as a separate exercise; the README links to relevant resources

## Consequences
- Cluster setup is a single `k3d cluster create` command
- All Kubernetes manifests, Helm charts, and GitOps workflows remain fully compatible with any standard K8s distribution (EKS, AKS, GKE)
- More project time available for differentiating features (OTel, Tempo, Canary, Chaos)
