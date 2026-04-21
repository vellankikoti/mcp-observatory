# mcp-observatory: Detailed Architecture

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         MCP SERVER FLEET (9+ servers)                      │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │ mcp-kubectl      │  │ mcp-grpc-server  │  │ mcp-postgres     │        │
│  │ (Python)         │  │ (Go)             │  │ (Python)         │        │
│  │ setup_mcp_       │  │ mco.Setup()      │  │ setup_mcp_       │        │
│  │ observability()  │  │                  │  │ observability()  │        │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
│           │                     │                     │                   │
│           │ OTel Spans + Metrics│                     │ OTel Spans       │
│           │ (http://localhost:4317)                   │ + Metrics        │
│           └──────────────────┬──────────────────────────────────┘        │
│                              │                                            │
└──────────────────────────────┼────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ OpenTelemetry       │
                    │ Collector           │
                    │ (otelcol)           │
                    │ localhost:4317      │
                    └────────┬────────┬───┘
         ┌──────────────────────────────────────┐
         │                                      │
┌────────▼─────────────────┐      ┌────────────▼────────────┐
│   PROMETHEUS SCRAPER     │      │   PROMETHEUS BACKEND    │
│   (scrapes OTel + app    │      │   prometheus:9090       │
│    metrics endpoints)    │      └────────────┬────────────┘
└────────┬─────────────────┘                   │
         │                                     │
         │ Time-series data                    │ PromQL queries
         │ (7 metrics below)                   │
         │                                     │
         └──────────────────┬──────────────────┘
                            │
        ┌───────────────────┼────────────────────┐
        │                   │                    │
┌───────▼────────┐  ┌───────▼─────────┐  ┌──────▼──────────────┐
│   GRAFANA       │  │  GO BACKEND API │  │ PROMETHEUS          │
│   (viz layer)   │  │  (query router) │  │ ALERTMANAGER        │
│   localhost:3000│  │  localhost:8080 │  │ (routing rules)     │
└───────┬────────┘  └───────┬─────────┘  └──────┬──────────────┘
        │                   │                    │
        │ Dashboard render  │ Query classify     │ Alerts fire
        │ + Panel queries   │ (DIRECT vs AI)     │ (Slack/PagerDuty)
        │ (4 dashboards)    │                    │
        │                   │ Prometheus API     │ Recording rules
        │                   │ queries            │ (frequency_rate)
        │                   │                    │
        │                   │ For AI path:       │
        │                   │ → Fetch metrics    │
        │                   │ → Fetch tool logs  │
        │                   │ → Fetch trace data │
        │                   │ → Call AI API      │
        │                   │ → Correlate        │
        │                   │ → Return analysis  │
        │                   │                    │
        └───────────────────┼────────────────────┘
                            │
                    ┌───────▼─────────┐
                    │  OPERATORS /    │
                    │  INCIDENT TEAMS │
                    │                 │
                    │ View dashboards │
                    │ Query APIs      │
                    │ Respond to      │
                    │ alerts          │
                    └─────────────────┘
```

---

## Hybrid Engine Classification

The query router classifies incoming queries into two paths based on complexity and reasoning requirements.

### Classification Logic

```
Query arrives at Go backend
        │
        ├─ Extract semantic keywords
        │  (error_rate, dashboard, latency, pool, server_name, tool_name, etc.)
        │
        ├─ Match against DIRECT_PATH patterns
        │  │
        │  ├─ MATCH: Infrastructure query (simple metric lookup)
        │  │          → DIRECT PATH (Prometheus API)
        │  │
        │  └─ NO MATCH: Complex reasoning needed
        │               → AI_PATH (cross-source correlation)
        │
        └─ Return classification + route
```

### Classification Examples (10+)

#### DIRECT PATH Queries (No AI Tokens)

1. **Query:** "What's the error rate of mcp-kubectl-server?"
   - **Classification:** DIRECT_PATH (infrastructure metric)
   - **Route:** Prometheus API → PromQL: `rate(mcp_tool_call_errors_total{server="mcp-kubectl-server"}[5m]) / rate(mcp_tool_call_total{server="mcp-kubectl-server"}[5m])`
   - **Response:** `{"error_rate": 0.032, "unit": "percentage", "window": "5m"}`
   - **Latency:** ~50ms, 0 AI tokens

2. **Query:** "Show me the dashboard for MCP server fleet"
   - **Classification:** DIRECT_PATH (dashboard lookup)
   - **Route:** Grafana API → GetDashboard(name="fleet-overview")
   - **Response:** `{"url": "http://grafana/d/fleet-overview", "title": "MCP Fleet Overview"}`
   - **Latency:** ~80ms, 0 AI tokens

3. **Query:** "What's the current connection pool utilization for mcp-postgres?"
   - **Classification:** DIRECT_PATH (gauge metric)
   - **Route:** Prometheus API → PromQL: `mcp_server_connection_pool_utilization{server="mcp-postgres"}`
   - **Response:** `{"utilization_percent": 87.3, "timestamp": "2026-04-20T14:32:10Z"}`
   - **Latency:** ~45ms, 0 AI tokens

4. **Query:** "List all MCP servers in the fleet"
   - **Classification:** DIRECT_PATH (metric enumeration)
   - **Route:** Prometheus API → PromQL: `count by (server) (mcp_tool_call_total)`
   - **Response:** `[{"server": "mcp-kubectl-server", "active": true}, {"server": "mcp-grpc-server", "active": true}, ...]`
   - **Latency:** ~55ms, 0 AI tokens

5. **Query:** "What are the p50, p95, p99 latencies for mcp-grpc-server?"
   - **Classification:** DIRECT_PATH (histogram percentile)
   - **Route:** Prometheus API → PromQL: `histogram_quantile(0.99, rate(mcp_tool_call_duration_seconds_bucket{server="mcp-grpc-server"}[5m]))`
   - **Response:** `{"p50_ms": 120, "p95_ms": 450, "p99_ms": 2100}`
   - **Latency:** ~65ms, 0 AI tokens

6. **Query:** "Show me tools with timeout errors in the last hour"
   - **Classification:** DIRECT_PATH (error type filter)
   - **Route:** Prometheus API → PromQL: `rate(mcp_tool_call_errors_total{error_type="timeout"}[1h])`
   - **Response:** `[{"tool": "tool_get_data", "errors_per_sec": 0.015}, ...]`
   - **Latency:** ~60ms, 0 AI tokens

7. **Query:** "What's the trace propagation failure rate for mcp-kubectl-server?"
   - **Classification:** DIRECT_PATH (counter metric)
   - **Route:** Prometheus API → PromQL: `rate(mcp_trace_propagation_failures_total{server="mcp-kubectl-server"}[5m])`
   - **Response:** `{"failure_rate": 0.001, "window": "5m"}`
   - **Latency:** ~50ms, 0 AI tokens

#### AI_PATH Queries (Reasoning Required)

8. **Query:** "Why did mcp-kubectl-server degrade last Tuesday?"
   - **Classification:** AI_PATH (incident correlation)
   - **Route:** 
     - Prometheus API → Fetch mcp-tool-call metrics for 2026-10-01
     - Prometheus API → Fetch mcp_tool_call_frequency_rate deviations for that day
     - Tool call logs → Fetch context around the degradation timeframe
     - Trace data → Correlation with propagation failures
     - Invoke AI reasoning → "Server started dropping calls at 14:23 UTC due to connection pool exhaustion, evidenced by pool utilization spike from 45% to 98% in 3 minutes. Tool call frequency then deviated 2.4 standard deviations below baseline, triggering abandonment alert."
   - **Latency:** ~1.8s, 2-4 AI reasoning tokens
   - **Response:** `{"root_cause": "connection_pool_exhaustion", "start_time": "2026-10-01T14:23:00Z", "impact": "dropped 342 tool calls over 14 minutes", "reasoning": "..."}`

9. **Query:** "Which MCP server should I investigate first based on current health?"
   - **Classification:** AI_PATH (ranking + reasoning)
   - **Route:**
     - Prometheus API → Fetch current error rates for all 9 servers
     - Prometheus API → Fetch connection pool utilization for all servers
     - Prometheus API → Fetch tool abandonment signals for all servers
     - Metrics aggregation → Compute impact score per server
     - Invoke AI reasoning → Rank servers by severity, explain reasoning
   - **Latency:** ~1.5s, 2-3 AI reasoning tokens
   - **Response:** `{"ranked_servers": [{"server": "mcp-postgres", "priority": 1, "reason": "pool at 94%, 5 abandoned tools, error rate 8.2%"}, ...], "summary": "mcp-postgres is degrading fastest..."}`

10. **Query:** "Correlate the failed incident response from 2026-10-15 with metric data"
    - **Classification:** AI_PATH (incident analysis)
    - **Route:**
      - Tool call logs → Fetch decisions made by AI agent during incident
      - Prometheus API → Fetch actual tool availability during incident window
      - Trace data → Correlate agent decisions with trace propagation failures
      - Invoke AI reasoning → Compare decisions against reality, identify where decisions diverged from facts
    - **Latency:** ~2.2s, 3-5 AI reasoning tokens
    - **Response:** `{"incident_date": "2026-10-15", "analysis": "Agent decided to use mcp-postgres at 09:15 UTC. Metrics show pool was 96% utilized at that time. Server had dropped 12 calls in previous 10min. Agent should have switched tools but didn't. Subsequent reports relied on fabricated data from mcp-postgres."}`

11. **Query:** "What changed in the MCP fleet between 2026-10-01 and 2026-10-15?"
    - **Classification:** AI_PATH (temporal correlation)
    - **Route:**
      - Prometheus API → Fetch baseline metrics for 2026-10-01
      - Prometheus API → Fetch current metrics for 2026-10-15
      - Configuration system → Fetch deployment changes, server restarts, config changes
      - Invoke AI reasoning → Correlate metric changes with infrastructure changes
    - **Latency:** ~2.0s, 2-3 AI reasoning tokens
    - **Response:** `{"summary": "3 significant changes: mcp-postgres upgraded from v1.2 to v1.4 (no metric impact), connection pool size decreased from 100 to 75 (caused 4% higher utilization), new tool added to mcp-kubectl-server (+15% call volume)"}`

12. **Query:** "Is there a systemic pattern in the tool abandonment alerts?"
    - **Classification:** AI_PATH (pattern analysis across time)
    - **Route:**
      - Prometheus API → Fetch all abandonment alerts from past 30 days
      - Tool call logs → Fetch context for each alert
      - Invoke AI reasoning → Identify patterns (time-of-day, specific tools, specific servers)
    - **Latency:** ~2.5s, 3-4 AI reasoning tokens
    - **Response:** `{"pattern": "tool abandonment occurs primarily between 14:00-16:00 UTC, affecting IO-heavy tools on mcp-postgres. Likely cause: afternoon batch jobs increase connection contention. Recommendation: scale connection pool or schedule batch jobs for 06:00-08:00 UTC."}`

---

## Go Backend Classifier Pseudocode

```go
package main

import "strings"

type QueryClassification struct {
    Path       string // "DIRECT_PATH" or "AI_PATH"
    Route      string // Target system (prometheus, grafana, ai_reasoning)
    Confidence float64 // 0.0-1.0
    Reasoning  string // Why this classification
}

type QueryRouter struct {
    prometheusClient PrometheusClient
    grafanaClient    GrafanaClient
    aiClient         AIReasoningClient
}

// Classify a user query into DIRECT_PATH or AI_PATH
func (qr *QueryRouter) ClassifyQuery(query string) QueryClassification {
    // Extract keywords
    keywords := ExtractKeywords(query)
    
    // Check DIRECT_PATH patterns
    if isDirectPathQuery(keywords, query) {
        return QueryClassification{
            Path:       "DIRECT_PATH",
            Route:      determineDirectRoute(keywords),
            Confidence: 0.95,
            Reasoning:  "Infrastructure metric lookup, single source, simple query",
        }
    }
    
    // Check AI_PATH patterns
    if isReasoningQuery(keywords, query) {
        return QueryClassification{
            Path:       "AI_PATH",
            Route:      "ai_reasoning",
            Confidence: 0.88,
            Reasoning:  "Cross-source correlation or temporal analysis required",
        }
    }
    
    // Default to AI_PATH (safer to over-reason than under-reason)
    return QueryClassification{
        Path:       "AI_PATH",
        Route:      "ai_reasoning",
        Confidence: 0.70,
        Reasoning:  "Unable to classify with high confidence, defaulting to AI path",
    }
}

// Check if query matches DIRECT_PATH patterns
func isDirectPathQuery(keywords []string, query string) bool {
    directPatterns := map[string][]string{
        "error_rate": {"What's", "what is", "show", "get"},
        "dashboard": {"show", "display", "get", "dashboard"},
        "pool": {"connection", "pool", "utilization"},
        "latency": {"latency", "duration", "p50", "p95", "p99"},
        "servers": {"list", "all", "servers", "fleet"},
        "trace_failure": {"trace", "propagation", "failure"},
    }
    
    // Check if any pattern keyword is present
    for keyword := range directPatterns {
        if containsKeyword(keywords, keyword) {
            // Check for negation words or temporal reasoning
            if !containsKeyword(keywords, "why", "reason", "cause", "correlation", "pattern", "between", "changed") {
                return true
            }
        }
    }
    
    return false
}

// Check if query requires AI reasoning
func isReasoningQuery(keywords []string, query string) bool {
    reasoningPatterns := []string{
        "why", "reason", "cause", "root cause",
        "correlation", "correlate", "pattern",
        "between", "changed", "change",
        "incident", "incident response",
        "which", "prioritize", "first",
        "decision", "compare", "analyze",
    }
    
    for _, pattern := range reasoningPatterns {
        if containsKeyword(keywords, pattern) {
            return true
        }
    }
    
    return false
}

// Determine which DIRECT route to use
func determineDirectRoute(keywords []string) string {
    if containsKeyword(keywords, "dashboard") {
        return "grafana"
    }
    return "prometheus"
}

// Route and execute query
func (qr *QueryRouter) RouteQuery(query string) (interface{}, error) {
    classification := qr.ClassifyQuery(query)
    
    switch classification.Path {
    case "DIRECT_PATH":
        return qr.executeDirect(query, classification.Route)
    case "AI_PATH":
        return qr.executeAIReasoning(query)
    default:
        return nil, fmt.Errorf("unknown path: %s", classification.Path)
    }
}

// Execute DIRECT_PATH queries (Prometheus/Grafana)
func (qr *QueryRouter) executeDirect(query string, route string) (interface{}, error) {
    switch route {
    case "prometheus":
        // Build PromQL from natural language query
        promql := buildPromQL(query)
        result, err := qr.prometheusClient.Query(promql)
        return result, err
    
    case "grafana":
        // Extract dashboard name and return URL
        dashboardName := extractDashboardName(query)
        url, err := qr.grafanaClient.GetDashboardURL(dashboardName)
        return map[string]string{"url": url}, err
    
    default:
        return nil, fmt.Errorf("unknown direct route: %s", route)
    }
}

// Execute AI_PATH queries (cross-source reasoning)
func (qr *QueryRouter) executeAIReasoning(query string) (interface{}, error) {
    // Step 1: Fetch all relevant data
    metrics := qr.prometheusClient.QueryMultiple(relevantMetricsFor(query))
    logs := qr.toolCallLogs.Fetch(timeRangeFrom(query))
    traces := qr.traceStore.Fetch(timeRangeFrom(query))
    
    // Step 2: Correlate data
    correlatedData := map[string]interface{}{
        "metrics": metrics,
        "logs": logs,
        "traces": traces,
    }
    
    // Step 3: Invoke AI reasoning
    analysis, err := qr.aiClient.Correlate(correlatedData, query)
    return analysis, err
}

// Helper: Extract keywords from query
func ExtractKeywords(query string) []string {
    lower := strings.ToLower(query)
    words := strings.Fields(lower)
    
    // Filter out stop words
    stopWords := map[string]bool{
        "the": true, "a": true, "an": true, "and": true, "or": true,
        "is": true, "are": true, "for": true, "of": true, "in": true,
    }
    
    var keywords []string
    for _, word := range words {
        if !stopWords[word] {
            keywords = append(keywords, word)
        }
    }
    return keywords
}

// Helper: Check if keywords contain target word
func containsKeyword(keywords []string, target ...string) bool {
    for _, t := range target {
        for _, k := range keywords {
            if strings.Contains(k, strings.ToLower(t)) {
                return true
            }
        }
    }
    return false
}
```

---

## Component Details

### 1. Go Backend API Server

**Purpose:** Query classifier and router. Accepts natural language queries, routes to appropriate backend (Prometheus, Grafana, or AI reasoning).

**Endpoints:**

```
GET /api/v1/query
  Query Params: q (query string), server (optional), start (optional), end (optional)
  Response: JSON with result
  Examples:
    - /api/v1/query?q=error_rate&server=mcp-kubectl-server
    - /api/v1/query?q=dashboard&query=fleet+overview
    - /api/v1/query?q=why+did+mcp-postgres+degrade&start=2026-10-01&end=2026-10-02

GET /api/v1/servers
  Response: List of all MCP servers with current status
  Response Schema: [{"name": "mcp-kubectl-server", "status": "healthy", "error_rate": 0.032, ...}, ...]

GET /api/v1/dashboards
  Response: List of available Grafana dashboards
  Response Schema: [{"id": "fleet-overview", "title": "MCP Fleet Overview", "url": "..."}, ...]

POST /api/v1/analyze-incident
  Body: {"start": "ISO8601", "end": "ISO8601"}
  Response: AI-generated incident analysis with root cause

GET /api/v1/health
  Response: Backend health status
  Response Schema: {"status": "healthy", "uptime": "24h12m", "prometheus": "ok", "ai_client": "ok"}
```

**Configuration (environment variables):**
```
PROMETHEUS_URL=http://prometheus:9090
GRAFANA_URL=http://grafana:3000
GRAFANA_API_KEY=xxxx
AI_API_KEY=xxxx (optional, only needed for AI path)
QUERY_TIMEOUT_MS=5000
DIRECT_PATH_TIMEOUT_MS=500
AI_PATH_TIMEOUT_MS=3000
LOG_LEVEL=info
```

**Dependencies:**
- Go 1.22+
- prometheus-client (go-prometheus v1.17+)
- grafana-sdk or custom HTTP client
- Optional: LLM SDK (claude-sdk-go, openai-go, etc.)

**Build:**
```bash
cd go-backend
go mod tidy
go build -o mcp-observatory-backend main.go
```

**Docker Image:**
```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o backend main.go

FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /app/backend /app/backend
EXPOSE 8080
CMD ["/app/backend"]
```

---

### 2. OpenTelemetry Instrumentation Library (Python)

**Purpose:** Emits OTel spans and metrics from inside MCP servers. Detects tool abandonment via frequency analysis.

**File:** `python-instrumentation/mcp_observatory/instrumentation.py`

**Main Entry Point:**
```python
from mcp_observatory.instrumentation import setup_mcp_observability

setup_mcp_observability(
    service_name="mcp-kubectl-server",
    prometheus_port=9091,
    otelsdk_enabled=True,
    otelsdk_endpoint="http://localhost:4317",
    tool_abandonment_baseline_window_minutes=60,
    tool_abandonment_deviation_threshold_std_devs=2.0,
    tool_abandonment_min_baseline_calls_per_hour=10,
)
```

**What it does:**
1. Sets up OpenTelemetry SDK (connects to OTel Collector)
2. Initializes Prometheus metrics endpoint
3. Wraps MCP tool call handling to emit spans and metrics
4. Runs tool abandonment detection algorithm in background

**Instrumentation Hooks:**
```python
# Call this BEFORE every tool execution
record_tool_call_start(tool_name="get_deployment", server="mcp-kubectl-server")

# Call this AFTER tool completes
record_tool_call_end(
    tool_name="get_deployment",
    server="mcp-kubectl-server",
    duration_seconds=0.245,
    status="success",
    error_type=None,
)

# Call on error
record_tool_call_error(
    tool_name="get_deployment",
    server="mcp-kubectl-server",
    error_type="timeout",  # or "server_error", "policy_rejection", "malformed_response"
)

# Call on trace propagation failure
record_trace_propagation_failure(server="mcp-kubectl-server")
```

**Tool Abandonment Detection Algorithm:**
```
Every 60 seconds:
  For each tool in the fleet:
    Count tool calls in the last 60 minutes: call_count
    
    If call_count >= 10:  # Minimum baseline to avoid false positives
      Calculate baseline: calls from 61-120 minutes ago
      Calculate current 1-hour deviation: (call_count - baseline) / stdev(baseline)
      
      If deviation > 2.0 std devs:
        Alert triggered: "Tool abandonment detected"
        Action: Create high-priority incident, notify operations
      Else if deviation < -2.0 std devs:
        Alert triggered: "Tool usage surge" (less critical)
    
    Else:
      # Not enough data for reliable baseline
      Skip this tool, wait for more calls
```

**Dependencies:**
```
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp==1.21.0
prometheus-client==0.20.0
```

---

### 3. Prometheus Metrics Library (Python)

**Purpose:** Exposes the 7 core metrics in Prometheus format.

**File:** `python-instrumentation/mcp_observatory/metrics.py`

**Metrics Registration:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Metric 1: Tool call total (counter)
mcp_tool_call_total = Counter(
    'mcp_tool_call_total',
    'Total MCP tool calls',
    labelnames=['tool', 'server', 'status'],  # status: success, error
)

# Metric 2: Tool call duration (histogram)
mcp_tool_call_duration_seconds = Histogram(
    'mcp_tool_call_duration_seconds',
    'MCP tool call latency in seconds',
    labelnames=['tool', 'server'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Metric 3: Tool call errors (counter)
mcp_tool_call_errors_total = Counter(
    'mcp_tool_call_errors_total',
    'Total MCP tool call errors',
    labelnames=['tool', 'server', 'error_type'],  # error_type: timeout, server_error, policy_rejection, malformed_response
)

# Metric 4: Server connections active (gauge)
mcp_server_connections_active = Gauge(
    'mcp_server_connections_active',
    'Active connections to MCP server',
    labelnames=['server'],
)

# Metric 5: Connection pool utilization (gauge)
mcp_server_connection_pool_utilization = Gauge(
    'mcp_server_connection_pool_utilization',
    'Connection pool utilization percentage',
    labelnames=['server'],
)

# Metric 7: Trace propagation failures (counter)
mcp_trace_propagation_failures_total = Counter(
    'mcp_trace_propagation_failures_total',
    'Failed OTel trace propagations',
    labelnames=['server'],
)

# Metric 6: Tool call frequency rate (recording rule, computed by Prometheus)
# Not registered here; computed via recording rule in prometheus.yml
```

**Usage Example:**
```python
# On tool call start
start_time = time.time()
mcp_tool_call_total.labels(tool="get_data", server="mcp-kubectl-server", status="started").inc()

try:
    result = run_tool()
    duration = time.time() - start_time
    
    # On success
    mcp_tool_call_total.labels(tool="get_data", server="mcp-kubectl-server", status="success").inc()
    mcp_tool_call_duration_seconds.labels(tool="get_data", server="mcp-kubectl-server").observe(duration)
    
except TimeoutError:
    mcp_tool_call_errors_total.labels(tool="get_data", server="mcp-kubectl-server", error_type="timeout").inc()
except ServerError:
    mcp_tool_call_errors_total.labels(tool="get_data", server="mcp-kubectl-server", error_type="server_error").inc()
```

**Prometheus Endpoint:**
```
GET /metrics
Response:
  mcp_tool_call_total{tool="get_data",server="mcp-kubectl-server",status="success"} 1523
  mcp_tool_call_total{tool="get_data",server="mcp-kubectl-server",status="error"} 45
  mcp_tool_call_duration_seconds_bucket{tool="get_data",server="mcp-kubectl-server",le="0.1"} 1200
  mcp_tool_call_duration_seconds_bucket{tool="get_data",server="mcp-kubectl-server",le="0.5"} 1450
  ...
```

---

### 4. Grafana Dashboard Suite

**Purpose:** Visualize all 7 metrics across 4 specialized dashboards.

#### Dashboard 1: Fleet Overview

**File:** `grafana/dashboards/fleet-overview.json`

**Panels:**
1. **Top-Left: Error Rate Trend** (line chart)
   - Y-axis: Error rate (%)
   - X-axis: Time
   - Query: `rate(mcp_tool_call_errors_total[5m]) / rate(mcp_tool_call_total[5m])`
   - Alert threshold line: 5%

2. **Top-Right: Tool Call Volume by Server** (stacked bar chart)
   - Y-axis: Calls per second
   - X-axis: Time
   - Query: `sum by (server) (rate(mcp_tool_call_total[1m]))`
   - Legend: Shows all 9 servers

3. **Middle-Left: Connection Pool Utilization** (gauge)
   - Current value: percentage
   - Query: `avg(mcp_server_connection_pool_utilization)`
   - Red threshold: >95%, Yellow: >75%

4. **Middle-Right: Tool Abandonment Alerts Fired** (stat)
   - Count of abandonment alerts in last 24h
   - Query: `count(increase(ALERTS{alertname="ToolAbandonment"}[24h]))`

5. **Bottom: Server Status Table**
   - Columns: Server Name, Error Rate, P99 Latency, Active Connections, Pool Utilization, Last Alert
   - Query: Individual queries for each column

#### Dashboard 2: Server Deep Dive

**File:** `grafana/dashboards/server-deep-dive.json`

**Features:**
- Variable selector to choose which server to drill into
- All charts auto-filter by selected server

**Panels:**
1. **Error Rate by Tool** (bar chart)
   - Query: `rate(mcp_tool_call_errors_total{server="$server"}[5m])`
   - Grouped by tool name

2. **Latency Percentiles** (line chart)
   - Query: `histogram_quantile(0.99, rate(mcp_tool_call_duration_seconds_bucket{server="$server"}[5m]))`
   - Shows p50, p95, p99

3. **Error Types Breakdown** (pie chart)
   - Query: `sum by (error_type) (mcp_tool_call_errors_total{server="$server"})`

4. **Connection Pool Over Time** (area chart)
   - Query: `mcp_server_connections_active{server="$server"}` and `mcp_server_connection_pool_utilization{server="$server"}`

5. **Trace Propagation Failures** (stat)
   - Query: `rate(mcp_trace_propagation_failures_total{server="$server"}[1h])`

#### Dashboard 3: Frequency Deviation Detector

**File:** `grafana/dashboards/frequency-deviation.json`

**Purpose:** Visualize tool abandonment signal in real-time

**Panels:**
1. **Abandonment Signal Heatmap** (heatmap)
   - Y-axis: Tool name
   - X-axis: Time
   - Color: Deviation in std devs (red = high deviation = abandonment)
   - Query: `mcp_tool_call_frequency_rate` (recording rule output)

2. **Current Deviations by Tool** (horizontal bar chart)
   - X-axis: Std deviation from baseline
   - Y-axis: Tool names
   - Alert line: 2.0 std devs

3. **Baseline vs Current Calls** (side-by-side comparison)
   - For each tool, show baseline call rate (gray) vs current rate (green/red)

#### Dashboard 4: Trace Explorer

**File:** `grafana/dashboards/trace-explorer.json`

**Purpose:** Correlate distributed traces with tool call events

**Panels:**
1. **Trace Propagation Timeline** (line chart)
   - Y-axis: Propagation success rate (%)
   - X-axis: Time
   - Query: `(1 - (mcp_trace_propagation_failures_total / mcp_tool_call_total)) * 100`

2. **Trace Failures by Server** (table)
   - Columns: Server, Failure Count, Failure Rate, Last Failure
   - Query: Individual per server

3. **Tool Call Events with Trace Status** (event histogram)
   - X-axis: Time
   - Bars colored by whether trace propagation succeeded/failed

---

### 5. Alert Rules

**File:** `prometheus/alert_rules.yml`

All 7 alert rules with Prometheus syntax:

```yaml
groups:
- name: mcp_observatory
  interval: 30s
  rules:
  
  # Alert 1: High Error Rate
  - alert: HighErrorRate
    expr: |
      (sum by (server) (rate(mcp_tool_call_errors_total[5m])) 
       / 
       sum by (server) (rate(mcp_tool_call_total[5m])))
      > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate on {{ $labels.server }}"
      description: "Error rate is {{ $value | humanizePercentage }}"
  
  # Alert 2: Connection Pool Exhaustion
  - alert: ConnectionPoolExhaustion
    expr: |
      mcp_server_connection_pool_utilization > 0.95
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Connection pool exhausted on {{ $labels.server }}"
      description: "Pool utilization is {{ $value | humanizePercentage }}"
  
  # Alert 3: Tool Abandonment (Frequency Deviation)
  - alert: ToolAbandonment
    expr: |
      mcp_tool_call_frequency_rate > 2.0
    for: 10m
    labels:
      severity: high
    annotations:
      summary: "Tool abandonment detected on {{ $labels.tool }}"
      description: "Frequency deviation is {{ $value }} std devs above baseline"
  
  # Alert 4: Long Latency
  - alert: LongLatency
    expr: |
      histogram_quantile(0.99, rate(mcp_tool_call_duration_seconds_bucket[5m])) > 2.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Long latency for {{ $labels.tool }} on {{ $labels.server }}"
      description: "P99 latency is {{ $value }}s"
  
  # Alert 5: Trace Propagation Failure
  - alert: TracePropagationFailure
    expr: |
      rate(mcp_trace_propagation_failures_total[5m]) > 0.01
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: "Trace propagation failures on {{ $labels.server }}"
      description: "Failure rate is {{ $value | humanizePercentage }}"
  
  # Alert 6: Server Unhealthy (No Metrics)
  - alert: ServerUnhealthy
    expr: |
      (time() - timestamp(mcp_tool_call_total{server="$server"})) > 300
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "No metrics received from {{ $labels.server }}"
      description: "Server may be down or instrumentation failed"
  
  # Alert 7: Malformed Responses
  - alert: ResponsesMalformed
    expr: |
      rate(mcp_tool_call_errors_total{error_type="malformed_response"}[5m]) > 0.001
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Malformed responses from {{ $labels.server }}"
      description: "{{ $value | humanizePercentage }} of responses are malformed"
```

**Alert Routing in AlertManager** (`prometheus/alertmanager.yml`):

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 30s
  repeat_interval: 24h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      repeat_interval: 1h
    
    - match:
        alertname: ToolAbandonment
      receiver: 'slack'
      repeat_interval: 2h

receivers:
  - name: 'default'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#mcp-alerts'
        title: 'MCP Observatory Alert'
        text: '{{ .CommonAnnotations.summary }}'
  
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        description: '{{ .CommonAnnotations.summary }}'
  
  - name: 'slack'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#mcp-abandonment-alerts'
        title: 'Tool Abandonment Detected'
        text: '{{ .CommonAnnotations.description }}'
```

---

### 6. Helm Chart Structure

**Directory:** `helm/mcp-observatory/`

#### Chart.yaml
```yaml
apiVersion: v2
name: mcp-observatory
description: Open observability platform for MCP server fleets
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords:
  - mcp
  - observability
  - monitoring
  - prometheus
  - grafana
maintainers:
  - name: MCP Observatory Team
    email: observability@example.com
```

#### values.yaml (Configurable Parameters)
```yaml
# Global settings
global:
  namespace: mcp-observatory
  domain: mcp-observatory.example.com

# Prometheus Configuration
prometheus:
  enabled: true
  image:
    repository: prom/prometheus
    tag: v2.48.1
  
  retention:
    days: 15  # How long to keep metrics
  
  scrapeConfigs:
    - job_name: mcp-servers
      static_configs:
        - targets:
          - 'mcp-kubectl-server:9091'
          - 'mcp-grpc-server:9092'
          - 'mcp-postgres:9093'
          # ... up to 9 servers
      scrape_interval: 15s
  
  recordingRules:
    enabled: true  # Enables mcp_tool_call_frequency_rate computation

# Grafana Configuration
grafana:
  enabled: true
  image:
    repository: grafana/grafana
    tag: 10.2.0
  
  adminPassword: admin
  
  dashboards:
    enabled: true
    # Four pre-built dashboards auto-imported
    - name: fleet-overview
      gnetId: null
      path: /etc/grafana/provisioning/dashboards/fleet-overview.json
    - name: server-deep-dive
      path: /etc/grafana/provisioning/dashboards/server-deep-dive.json
    - name: frequency-deviation
      path: /etc/grafana/provisioning/dashboards/frequency-deviation.json
    - name: trace-explorer
      path: /etc/grafana/provisioning/dashboards/trace-explorer.json
  
  datasources:
    - name: Prometheus
      type: prometheus
      url: http://prometheus:9090
      isDefault: true

# Go Backend Configuration
backend:
  enabled: true
  image:
    repository: mcp-observatory/backend
    tag: 0.1.0
  
  replicas: 2
  
  config:
    prometheusUrl: http://prometheus:9090
    grafanaUrl: http://grafana:3000
    queryTimeoutMs: 5000
    directPathTimeoutMs: 500
    aiPathTimeoutMs: 3000
    logLevel: info

# AlertManager Configuration
alertmanager:
  enabled: true
  image:
    repository: prom/alertmanager
    tag: v0.26.0
  
  config:
    global:
      resolve_timeout: 5m
    
    receivers:
      - name: 'slack'
        slack_configs:
          - api_url: '${SLACK_WEBHOOK_URL}'
            channel: '#mcp-alerts'
      
      - name: 'pagerduty'
        pagerduty_configs:
          - service_key: '${PAGERDUTY_SERVICE_KEY}'

# Ingress Configuration
ingress:
  enabled: true
  className: nginx
  
  hosts:
    - host: grafana.mcp-observatory.example.com
      paths:
        - path: /
          pathType: Prefix
          backend: grafana
    
    - host: prometheus.mcp-observatory.example.com
      paths:
        - path: /
          pathType: Prefix
          backend: prometheus
    
    - host: api.mcp-observatory.example.com
      paths:
        - path: /
          pathType: Prefix
          backend: backend
  
  tls:
    enabled: true
    secretName: mcp-observatory-tls

# Storage Configuration
persistence:
  prometheus:
    enabled: true
    size: 50Gi
    storageClass: standard
```

#### Templates Directory

**templates/prometheus-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: {{ .Values.prometheus.image.repository }}:{{ .Values.prometheus.image.tag }}
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: storage
          mountPath: /prometheus
      volumes:
      - name: config
        configMap:
          name: prometheus-config
      - name: storage
        persistentVolumeClaim:
          claimName: prometheus-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: {{ .Values.global.namespace }}
spec:
  ports:
  - port: 9090
    targetPort: 9090
  selector:
    app: prometheus
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: prometheus-pvc
  namespace: {{ .Values.global.namespace }}
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: {{ .Values.persistence.prometheus.storageClass }}
  resources:
    requests:
      storage: {{ .Values.persistence.prometheus.size }}
```

**templates/grafana-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: {{ .Values.grafana.image.repository }}:{{ .Values.grafana.image.tag }}
        ports:
        - containerPort: 3000
        env:
        - name: GF_SECURITY_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: grafana-secrets
              key: admin-password
        volumeMounts:
        - name: provisioning
          mountPath: /etc/grafana/provisioning
        - name: dashboards
          mountPath: /etc/grafana/dashboards
      volumes:
      - name: provisioning
        configMap:
          name: grafana-provisioning
      - name: dashboards
        configMap:
          name: grafana-dashboards
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: {{ .Values.global.namespace }}
spec:
  ports:
  - port: 80
    targetPort: 3000
  selector:
    app: grafana
```

**templates/backend-deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-observatory-backend
  namespace: {{ .Values.global.namespace }}
spec:
  replicas: {{ .Values.backend.replicas }}
  selector:
    matchLabels:
      app: mcp-observatory-backend
  template:
    metadata:
      labels:
        app: mcp-observatory-backend
    spec:
      containers:
      - name: backend
        image: {{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag }}
        ports:
        - containerPort: 8080
        env:
        - name: PROMETHEUS_URL
          value: {{ .Values.backend.config.prometheusUrl }}
        - name: GRAFANA_URL
          value: {{ .Values.backend.config.grafanaUrl }}
        - name: QUERY_TIMEOUT_MS
          value: "{{ .Values.backend.config.queryTimeoutMs }}"
        - name: LOG_LEVEL
          value: {{ .Values.backend.config.logLevel }}
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-observatory-backend
  namespace: {{ .Values.global.namespace }}
spec:
  ports:
  - port: 8080
    targetPort: 8080
  selector:
    app: mcp-observatory-backend
```

**templates/configmaps.yaml**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: {{ .Values.global.namespace }}
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    scrape_configs:
      {{- range .Values.prometheus.scrapeConfigs }}
      - job_name: {{ .job_name }}
        static_configs:
          - targets:
            {{- range .static_configs[0].targets }}
            - '{{ . }}'
            {{- end }}
        scrape_interval: {{ .scrape_interval | default "15s" }}
      {{- end }}
    
    rule_files:
      - '/etc/prometheus/recording_rules.yml'
      - '/etc/prometheus/alert_rules.yml'
  
  recording_rules.yml: |
    # Tool call frequency rate (for abandonment detection)
    groups:
    - name: mcp_frequency_rate
      interval: 60s
      rules:
      - record: mcp_tool_call_frequency_rate
        expr: |
          abs(
            (rate(mcp_tool_call_total[1h]) - rate(mcp_tool_call_total[61m:1h])) 
            / 
            stddev_over_time(rate(mcp_tool_call_total[1h])[60m:1h])
          )
  
  alert_rules.yml: |
    # (7 alert rules as defined above)
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-provisioning
  namespace: {{ .Values.global.namespace }}
data:
  datasources.yml: |
    apiVersion: 1
    datasources:
    - name: Prometheus
      type: prometheus
      url: http://prometheus:9090
      isDefault: true
  
  dashboards.yml: |
    apiVersion: 1
    providers:
    - name: 'mcp-dashboards'
      orgId: 1
      folder: ''
      type: file
      disableDeletion: false
      options:
        path: /etc/grafana/dashboards
```

**templates/ingress.yaml**
```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-observatory
  namespace: {{ .Values.global.namespace }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  rules:
  {{- range .Values.ingress.hosts }}
  - host: {{ .host }}
    http:
      paths:
      {{- range .paths }}
      - path: {{ .path }}
        pathType: {{ .pathType }}
        backend:
          service:
            name: {{ .backend }}
            port:
              number: {{ if eq .backend "grafana" }}80{{ else if eq .backend "prometheus" }}9090{{ else }}8080{{ end }}
      {{- end }}
  {{- end }}
  {{- if .Values.ingress.tls.enabled }}
  tls:
  - hosts:
    {{- range .Values.ingress.hosts }}
    - {{ .host }}
    {{- end }}
    secretName: {{ .Values.ingress.tls.secretName }}
  {{- end }}
{{- end }}
```

---

## All 7 Prometheus Metrics (Detailed)

### 1. mcp_tool_call_total
**Type:** Counter
**Labels:** tool, server, status
**Description:** Total count of MCP tool calls
**Example:**
```
mcp_tool_call_total{tool="get_deployment",server="mcp-kubectl-server",status="success"} 15234
mcp_tool_call_total{tool="get_deployment",server="mcp-kubectl-server",status="error"} 320
```
**Usage:** Rate of tool calls: `rate(mcp_tool_call_total[5m])`

### 2. mcp_tool_call_duration_seconds
**Type:** Histogram (with buckets)
**Labels:** tool, server
**Buckets:** [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0] seconds
**Description:** Latency distribution of tool calls
**Example:**
```
mcp_tool_call_duration_seconds_bucket{tool="get_data",server="mcp-kubectl-server",le="0.1"} 10234
mcp_tool_call_duration_seconds_bucket{tool="get_data",server="mcp-kubectl-server",le="0.5"} 14123
mcp_tool_call_duration_seconds_bucket{tool="get_data",server="mcp-kubectl-server",le="+Inf"} 15234
mcp_tool_call_duration_seconds_sum{tool="get_data",server="mcp-kubectl-server"} 3456.78
mcp_tool_call_duration_seconds_count{tool="get_data",server="mcp-kubectl-server"} 15234
```
**Usage:** P99 latency: `histogram_quantile(0.99, rate(mcp_tool_call_duration_seconds_bucket[5m]))`

### 3. mcp_tool_call_errors_total
**Type:** Counter
**Labels:** tool, server, error_type
**Error Types:** timeout, server_error, policy_rejection, malformed_response
**Description:** Total count of tool call errors by type
**Example:**
```
mcp_tool_call_errors_total{tool="get_data",server="mcp-kubectl-server",error_type="timeout"} 45
mcp_tool_call_errors_total{tool="get_data",server="mcp-kubectl-server",error_type="server_error"} 120
mcp_tool_call_errors_total{tool="get_data",server="mcp-kubectl-server",error_type="policy_rejection"} 23
mcp_tool_call_errors_total{tool="get_data",server="mcp-kubectl-server",error_type="malformed_response"} 8
```
**Usage:** Error rate by type: `rate(mcp_tool_call_errors_total{error_type="timeout"}[5m])`

### 4. mcp_server_connections_active
**Type:** Gauge
**Labels:** server
**Description:** Current number of active connections to an MCP server
**Example:**
```
mcp_server_connections_active{server="mcp-kubectl-server"} 42
mcp_server_connections_active{server="mcp-grpc-server"} 58
mcp_server_connections_active{server="mcp-postgres"} 94
```
**Usage:** Monitor for connection leaks, identify bottlenecks

### 5. mcp_server_connection_pool_utilization
**Type:** Gauge
**Labels:** server
**Units:** Percentage (0-100)
**Description:** How much of the connection pool is currently in use
**Example:**
```
mcp_server_connection_pool_utilization{server="mcp-kubectl-server"} 42.5
mcp_server_connection_pool_utilization{server="mcp-grpc-server"} 58.2
mcp_server_connection_pool_utilization{server="mcp-postgres"} 94.8
```
**Alert:** Trigger when > 95%
**Usage:** Capacity planning, identify resource constraints

### 6. mcp_tool_call_frequency_rate
**Type:** Recording Rule Output (computed from other metrics)
**Description:** Frequency deviation in standard deviations (the abandonment signal)
**Computation:** (current_1h_rate - baseline_rate) / stdev(baseline)
**Example:**
```
mcp_tool_call_frequency_rate{tool="get_data",server="mcp-kubectl-server"} 2.4
mcp_tool_call_frequency_rate{tool="list_pods",server="mcp-kubectl-server"} 1.1
mcp_tool_call_frequency_rate{tool="apply_config",server="mcp-kubectl-server"} 3.8
```
**Alert:** Trigger when > 2.0 (tool abandonment detected)
**Interpretation:**
- Value > 2.0: Tool is being used LESS than normal (agent routing around it)
- Value < -2.0: Tool is being used MORE than normal (surge, possibly compensating for other tools)
- Value between -2.0 and 2.0: Normal operation

### 7. mcp_trace_propagation_failures_total
**Type:** Counter
**Labels:** server
**Description:** Count of failed OpenTelemetry trace propagations
**Example:**
```
mcp_trace_propagation_failures_total{server="mcp-kubectl-server"} 3
mcp_trace_propagation_failures_total{server="mcp-grpc-server"} 12
```
**Usage:** Trace propagation failure rate: `rate(mcp_trace_propagation_failures_total[5m])`
**Alert:** Trigger when > 1% failure rate

---

## Tool Abandonment Detection Algorithm (Detailed)

```
Input: mcp_tool_call_total metrics
Output: Alerts when tool abandonment detected

Configuration Parameters:
  baseline_window = 60 minutes
  deviation_threshold = 2.0 standard deviations
  minimum_baseline_calls = 10 calls per hour
  evaluation_interval = 60 seconds

Algorithm (runs every evaluation_interval):

  For each tool in the fleet:
    
    Step 1: Collect baseline data
      baseline_calls_60_to_120min_ago = sum(mcp_tool_call_total[60m:120m])
      
      If baseline_calls < minimum_baseline_calls:
        # Not enough data; skip this tool this iteration
        Continue to next tool
    
    Step 2: Collect current data
      current_calls_last_60min = sum(mcp_tool_call_total[60m])
    
    Step 3: Calculate baseline statistics
      baseline_mean = average(mcp_tool_call_total[60m:480m])  # Average over last 8 hours
      baseline_stdev = stddev(mcp_tool_call_total[60m:480m])
      
      If baseline_stdev == 0:
        # No variance in baseline; tool usage is consistent
        # Minor fluctuations won't trigger alerts
        baseline_stdev = 0.1 * baseline_mean  # Use 10% of mean as minimum stdev
    
    Step 4: Calculate deviation
      deviation = (current_calls_last_60min - baseline_mean) / baseline_stdev
      
      If deviation > baseline_mean:
        # Avoid division by very small numbers
        deviation = 10.0  # Cap at 10 std devs
    
    Step 5: Check threshold
      If deviation > deviation_threshold:
        # Tool is being used LESS than normal
        Alert("ToolAbandonment", {
          tool: tool_name,
          server: server_name,
          deviation_std_devs: deviation,
          baseline_calls_per_hour: baseline_mean,
          current_calls_per_hour: current_calls_last_60min,
          severity: "high",
          reason: "Tool usage significantly below baseline; agent may be routing around degraded server"
        })
      
      Else if deviation < -deviation_threshold:
        # Tool is being used MORE than normal (less critical)
        Alert("ToolUsageSurge", {
          tool: tool_name,
          server: server_name,
          deviation_std_devs: deviation,
          reason: "Unusual increase in tool usage; possible compensatory behavior"
        })
      
      Else:
        # Normal operation
        Continue to next tool

  End loop

Record mcp_tool_call_frequency_rate metric with computed deviation values
```

**Why This Approach?**

1. **Baseline Window (60 min):** Captures the tool's normal usage pattern for that hour of day
2. **8-hour Statistics:** Accounts for hour-to-hour variation without over-fitting to temporary spikes
3. **2 Std Dev Threshold:** Statistically significant (95th percentile in normal distribution), reduces false positives
4. **Minimum 10 Calls/Hour:** Avoids noisy alerts for rarely-used tools
5. **Capped Stdev:** Prevents divide-by-zero and extreme sensitivity on unused tools

**Real-World Example:**

```
Tool: get_pod_logs
Server: mcp-kubectl-server

Hour 0 (06:00-07:00): 150 calls
Hour 1 (07:00-08:00): 155 calls
Hour 2 (08:00-09:00): 148 calls
Hour 3 (09:00-10:00): 152 calls
Hour 4 (10:00-11:00): 30 calls  ← Server started dropping calls at 10:30
Hour 5 (11:00-12:00): 25 calls
Hour 6 (12:00-13:00): 28 calls

Baseline mean = (150+155+148+152)/4 = 151.25 calls/hour
Baseline stdev = ~2.87 calls/hour

Current (Hour 4): 30 calls/hour
Deviation = (30 - 151.25) / 2.87 = -42.3 std devs

Alert triggered: ToolAbandonment on get_pod_logs
Reason: Tool usage dropped to 20% of baseline; check server health
```

---

## Directory Structure (Complete)

```
mcp-observatory/
│
├── README.md                                 (User-facing documentation)
├── PROPOSAL.md                               (CFP submission for MCP Dev Summit)
├── ARCHITECTURE.md                           (This file)
├── LICENSE                                   (Apache 2.0)
├── .gitignore
│
├── go-backend/                               (Go query router + API)
│   ├── main.go                               (Entry point, server setup)
│   ├── router.go                             (Query classifier, routing logic)
│   ├── prometheus.go                         (Prometheus client, PromQL builder)
│   ├── grafana.go                            (Grafana API client)
│   ├── ai_reasoning.go                       (AI cross-source correlation)
│   ├── types.go                              (Shared types)
│   ├── go.mod                                (Dependency manifest)
│   ├── go.sum
│   ├── Dockerfile
│   └── README.md                             (Build & deploy instructions)
│
├── python-instrumentation/                   (Python SDK for MCP servers)
│   ├── mcp_observatory/
│   │   ├── __init__.py
│   │   ├── instrumentation.py                (Main entry: setup_mcp_observability)
│   │   ├── metrics.py                        (Prometheus metrics definitions)
│   │   ├── otel.py                           (OpenTelemetry setup)
│   │   ├── tool_abandonment.py               (Frequency detection algorithm)
│   │   └── types.py
│   ├── setup.py                              (Package definition)
│   ├── pyproject.toml                        (Modern Python packaging)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── prometheus/
│   ├── prometheus.yml                        (Scrape config for 9 servers)
│   ├── recording_rules.yml                   (mcp_tool_call_frequency_rate rule)
│   ├── alert_rules.yml                       (7 alert rules)
│   └── Dockerfile
│
├── grafana/
│   ├── dashboards/
│   │   ├── fleet-overview.json               (Dashboard 1: Fleet status)
│   │   ├── server-deep-dive.json             (Dashboard 2: Per-server detail)
│   │   ├── frequency-deviation.json          (Dashboard 3: Abandonment signal)
│   │   └── trace-explorer.json               (Dashboard 4: Distributed traces)
│   ├── datasources/
│   │   └── prometheus.yml                    (Prometheus datasource config)
│   └── Dockerfile
│
├── helm/
│   └── mcp-observatory/
│       ├── Chart.yaml                        (Helm chart metadata)
│       ├── values.yaml                       (All configurable parameters)
│       ├── values-dev.yaml                   (Development overrides)
│       ├── values-prod.yaml                  (Production overrides)
│       ├── templates/
│       │   ├── prometheus-deployment.yaml    (Prometheus K8s resources)
│       │   ├── grafana-deployment.yaml       (Grafana K8s resources)
│       │   ├── backend-deployment.yaml       (Go backend K8s resources)
│       │   ├── alertmanager-deployment.yaml  (AlertManager K8s resources)
│       │   ├── configmaps.yaml               (Prometheus/AlertManager config)
│       │   ├── ingress.yaml                  (Kubernetes Ingress)
│       │   ├── rbac.yaml                     (RBAC roles for MCP servers)
│       │   └── _helpers.tpl                  (Helm template helpers)
│       └── README.md                         (Helm chart usage)
│
├── test/
│   ├── mock-servers/
│   │   ├── mock_mcp_server_1.py              (Dummy MCP server for testing)
│   │   ├── mock_mcp_server_2.py
│   │   ├── ...
│   │   └── docker-compose.yaml               (Spin up 9 mock servers locally)
│   │
│   ├── e2e/
│   │   ├── test_direct_queries.py            (Test Prometheus path queries)
│   │   ├── test_ai_queries.py                (Test AI path correlation)
│   │   ├── test_abandonment_detection.py     (Test frequency deviation alerting)
│   │   └── conftest.py
│   │
│   ├── load/
│   │   ├── load_test.py                      (Simulate high tool call volume)
│   │   ├── connection_pool_exhaustion.py     (Simulate pool saturation)
│   │   └── latency_simulation.py             (Simulate degraded servers)
│   │
│   └── README.md                             (Test suite documentation)
│
├── docs/
│   ├── production-guide.md                   (Deployment runbook)
│   ├── contributing.md                       (How to contribute)
│   ├── api-reference.md                      (Go backend API docs)
│   ├── troubleshooting.md                    (Common issues & fixes)
│   └── metrics-reference.md                  (All 7 metrics explained)
│
├── examples/
│   ├── python-instrumentation-example.py     (How to use Python SDK)
│   ├── go-instrumentation-example.go         (How to use Go SDK)
│   ├── helm-deploy.sh                        (One-liner Helm deployment)
│   └── local-dev-docker-compose.yaml         (Local testing setup)
│
├── .github/
│   └── workflows/
│       ├── build.yml                         (Build containers on push)
│       ├── test.yml                          (Run test suite)
│       └── publish.yml                       (Publish to registries)
│
├── Makefile                                  (Common commands)
│   (Targets: build, test, deploy, clean, etc.)
│
└── CONTRIBUTING.md                           (Community guidelines)
```

---

## Deployment Models

### Model 1: Kubernetes (Recommended)

```bash
helm install mcp-observatory ./helm/mcp-observatory \
  --namespace mcp-observatory --create-namespace
```

Deploys:
- Prometheus StatefulSet (1 replica, 50GB PVC)
- Grafana Deployment (1 replica)
- Go Backend Deployment (2 replicas for HA)
- AlertManager Deployment (1 replica)
- Ingress (for external access)

### Model 2: Docker Compose (Local Development)

```bash
docker-compose -f examples/local-dev-docker-compose.yaml up
```

Deploys:
- Prometheus (localhost:9090)
- Grafana (localhost:3000)
- Go Backend (localhost:8080)
- 9 mock MCP servers (localhost:9091-9099)

### Model 3: Single Binary (Standalone)

For teams without Kubernetes:

```bash
# Build all components into single binary
./go-backend/build-standalone.sh

# Run with embedded Prometheus, Grafana, AlertManager
./mcp-observatory-standalone \
  --prometheus-retention=720h \
  --grafana-admin-password=secretpassword
```

---

## Data Flow Examples

### Scenario 1: Direct Query (Error Rate)

```
User: "What's the error rate of mcp-kubectl-server?"
        │
        ↓
Go Backend /api/v1/query endpoint
        │
        ├─ Extract keywords: ["error", "rate", "mcp-kubectl-server"]
        │
        ├─ Check DIRECT_PATH patterns: ✓ matches "error_rate"
        │
        ├─ Route: Prometheus
        │
        ├─ Build PromQL:
        │  rate(mcp_tool_call_errors_total{server="mcp-kubectl-server"}[5m]) 
        │  / 
        │  rate(mcp_tool_call_total{server="mcp-kubectl-server"}[5m])
        │
        ├─ Execute: ~45ms latency
        │
        └─ Response: {"error_rate": 0.032, "unit": "percentage"}
```

### Scenario 2: AI Path (Incident Correlation)

```
User: "Why did mcp-kubectl-server degrade on 2026-10-01?"
        │
        ↓
Go Backend /api/v1/query endpoint
        │
        ├─ Extract keywords: ["why", "degrade", "mcp-kubectl-server", "2026-10-01"]
        │
        ├─ Check DIRECT_PATH patterns: ✗ no match
        ├─ Check AI_PATH patterns: ✓ matches "why"
        │
        ├─ Route: AI Reasoning
        │
        ├─ Fetch data:
        │  ├─ Prometheus: mcp_tool_call_total, mcp_tool_call_errors_total [2026-10-01]
        │  ├─ Prometheus: mcp_server_connection_pool_utilization [2026-10-01]
        │  ├─ Prometheus: mcp_tool_call_frequency_rate [2026-10-01]
        │  ├─ Tool call logs: All calls to mcp-kubectl-server [2026-10-01]
        │  └─ Trace store: All trace propagation failures [2026-10-01]
        │
        ├─ Correlate:
        │  - 14:23 UTC: error rate jumped from 0.8% to 8.2%
        │  - 14:23 UTC: connection pool utilization jumped from 45% to 98%
        │  - 14:25 UTC: tool_call_frequency_rate deviated 2.4 std devs
        │  - 14:30 UTC: trace propagation failures increased 10x
        │
        ├─ Invoke AI reasoning:
        │  "Server mcp-kubectl-server started dropping tool calls at 14:23 UTC.
        │   Connection pool exhaustion (utilization 98%) likely culprit.
        │   Agent detected degradation and routed around it by 14:30 UTC.
        │   ...recommendations..."
        │
        ├─ Execute: ~2.1s latency, 3 AI reasoning tokens
        │
        └─ Response: {"root_cause": "connection_pool_exhaustion", "analysis": "..."}
```

### Scenario 3: Tool Abandonment Detection (Automatic Alert)

```
Prometheus evaluation loop (every 30s):
        │
        ├─ Query: mcp_tool_call_total for each tool [past 60 minutes]
        │
        ├─ For tool "get_pod_logs":
        │  ├─ Baseline (hours 0-3): 150 calls/hour average
        │  ├─ Current (hour 4): 28 calls/hour
        │  ├─ Deviation: -42.3 std devs (VERY significant)
        │  └─ Deviation > 2.0? YES
        │
        ├─ Fire alert: ToolAbandonment
        │  └─ Alert tags: tool=get_pod_logs, server=mcp-kubectl-server, severity=high
        │
        ├─ AlertManager receives alert
        │  ├─ Check routing rules
        │  ├─ Severity: high → send to Slack + PagerDuty
        │  └─ Channel: #mcp-abandonment-alerts
        │
        └─ Operator receives Slack notification:
            "⚠️ Tool Abandonment Detected
             Tool: get_pod_logs
             Server: mcp-kubectl-server
             Deviation: 42.3 std devs below baseline
             Baseline rate: 150 calls/hour
             Current rate: 28 calls/hour
             Likely cause: Server degradation, check connection pool"
```

---

## Dependency Versions (Pinned)

### Python Dependencies
```
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp==1.21.0
prometheus-client==0.20.0
fastapi==0.110.0
pydantic==2.6.0
uvicorn==0.28.0
requests==2.31.0
```

### Go Dependencies
```
github.com/prometheus/client_golang v1.19.1
github.com/prometheus/common v0.56.0
github.com/prometheus/prometheus v0.48.1
github.com/grafana/grafana-api-golang-client v0.23.0
github.com/go-resty/resty/v2 v2.11.0
```

### Container Versions
```
Prometheus: prom/prometheus:v2.48.1
Grafana: grafana/grafana:10.2.0
OpenTelemetry Collector: otel/opentelemetry-collector:v0.95.0
AlertManager: prom/alertmanager:v0.26.0
```

---

## Summary

This architecture provides:

1. **Semantic Observability** — The 7 metrics are designed for MCP's access patterns
2. **Abandonment Detection** — Unique algorithm catches silent failures before they propagate
3. **Hybrid Query Engine** — Direct queries stay fast and token-free; AI reserved for real reasoning
4. **Production-Ready** — Prometheus + Grafana + Kubernetes-native
5. **Fully Extensible** — Every component is modular, open-source, replaceable

The platform is designed for another LLM session (or developer) to build completely from these specifications. Every file path, metric name, alert rule, and algorithm detail is included.
