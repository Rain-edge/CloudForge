# ADR-002: Use ArgoCD over Flux for GitOps

## Status
Accepted

## Context
The project needs a GitOps tool to automatically synchronize the cluster state with the Git repository. Two CNCF-graduated options exist: ArgoCD and Flux CD.

## Decision
Use **ArgoCD**.

## Rationale
1. **Web UI**: ArgoCD provides a built-in web dashboard showing application health, sync status, and resource tree. This is valuable for demonstrations and interview presentations — you can visually show "here's my app, it's synced, this is the diff."
2. **Simplicity for single-cluster**: Flux's multi-tenancy model (Kustomize overlays, Image Automation) adds complexity for a single-cluster demo project. ArgoCD's Application CRD maps directly to a Helm chart path.
3. **Market presence**: ArgoCD has broader adoption in job postings and enterprise environments (Red Hat OpenShift GitOps is ArgoCD-based).
4. **Canary integration**: ArgoCD integrates with Argo Rollouts for progressive delivery (future roadmap).

## Tradeoffs
- **Flux advantage**: Flux's image automation controller can automatically update image tags when new versions are pushed to the registry. ArgoCD requires explicit manifest updates (or Argo CD Image Updater).
- **Mitigation**: The GitHub Actions CI pipeline includes a `create-manifest` job that creates multi-arch manifests. For a demo project, explicit image tag updates in the Git repo provide a clearer audit trail and are easier to explain.

## Consequences
- ArgoCD monitors the `chart/` directory in the Git repo
- Any push to `main` triggers automatic sync within 3 minutes
- The ArgoCD web UI is accessible via `kubectl port-forward` for demonstrations
