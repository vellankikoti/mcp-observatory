{{- define "observatory-server.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name "observatory-server" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "observatory-server.labels" -}}
app.kubernetes.io/name: observatory-server
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "observatory-server.selectorLabels" -}}
app.kubernetes.io/name: observatory-server
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "observatory-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ include "observatory-server.fullname" . }}
{{- else -}}
default
{{- end -}}
{{- end -}}

{{- define "observatory-server.containerSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
{{- end -}}
