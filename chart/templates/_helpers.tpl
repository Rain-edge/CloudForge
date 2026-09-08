{{- /*
  辅助函数：生成符合 K8s 命名规范的资源名
  使用：{{ include "cloudforge.name" . }}
*/ -}}
{{- define "cloudforge.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- /*
  完整资源名：Release.Name + 应用名（Helm 惯用做法，避免多 Release 命名冲突）
  使用：{{ include "cloudforge.fullname" . }}
*/ -}}
{{- define "cloudforge.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" (include "cloudforge.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- /*
  标准标签集合：Helm 推荐的 app.kubernetes.io/* 标签
  kubectl / ArgoCD / 监控采集器都据此识别资源归属
*/ -}}
{{- define "cloudforge.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "cloudforge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
