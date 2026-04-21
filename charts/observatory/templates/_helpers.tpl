{{- define "observatory.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name "observatory" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "observatory.labels" -}}
app.kubernetes.io/name: observatory
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "observatory.selectorLabels" -}}
app.kubernetes.io/name: observatory
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "observatory.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ include "observatory.fullname" . }}
{{- else -}}
default
{{- end -}}
{{- end -}}

{{- define "observatory.containerSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
{{- end -}}
