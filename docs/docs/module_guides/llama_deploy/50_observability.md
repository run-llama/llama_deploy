# Observability

LlamaDeployment provides comprehensive observability capabilities through distributed tracing and metrics collection.
This allows you to monitor workflow execution, track performance, and debug issues across your distributed deployment.

## Overview

LlamaDeployment supports two main observability features:

1. **Distributed Tracing** - Track request flows across services using OpenTelemetry
2. **Metrics Collection** - Monitor system performance with Prometheus metrics

## Distributed Tracing

Distributed tracing provides end-to-end visibility into workflow execution across all components in your deployment.
Traces show the complete journey of a request from the API server through message queues to workflow completion.

### What Gets Traced

- **Control Plane**: Service registration, task orchestration, and session management
- **Workflow Services**: Complete workflow execution lifecycle including state loading, workflow running, event
  streaming, and result publishing
- **Message Queues**: Message publishing and consumption with trace context propagation

### Configuration

Tracing is disabled by default and can be enabled through environment variables:

```bash
# Enable tracing
export LLAMA_DEPLOY_APISERVER_TRACING_ENABLED=true

# Set service name (default: llama-deploy-apiserver)
export LLAMA_DEPLOY_APISERVER_TRACING_SERVICE_NAME=my-api-server

# Configure exporter (console, jaeger, otlp)
export LLAMA_DEPLOY_APISERVER_TRACING_EXPORTER=jaeger
export LLAMA_DEPLOY_APISERVER_TRACING_ENDPOINT=localhost:14268

# Configure sampling rate (0.0 to 1.0)
export LLAMA_DEPLOY_APISERVER_TRACING_SAMPLE_RATE=0.1
```

### Supported Exporters

#### Console Exporter
Prints traces to the console - useful for development:

```bash
export LLAMA_DEPLOY_APISERVER_TRACING_EXPORTER=console
```

#### OTLP Exporter
Exports traces using OpenTelemetry Protocol (works with many backends like Jaeger):

```bash
export LLAMA_DEPLOY_APISERVER_TRACING_EXPORTER=otlp
export LLAMA_DEPLOY_APISERVER_TRACING_ENDPOINT=http://localhost:4317
```

### Setting Up Jaeger

To set up Jaeger for trace collection and visualization:

```bash
# Run Jaeger all-in-one container
docker run --rm -d \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 9411:9411 \
  jaegertracing/all-in-one:latest

# Configure LlamaDeployment to use Jaeger
export LLAMA_DEPLOY_APISERVER_TRACING_ENABLED=true
export LLAMA_DEPLOY_APISERVER_TRACING_EXPORTER=otlp
export LLAMA_DEPLOY_APISERVER_TRACING_ENDPOINT=http://localhost:4317
```

Access the Jaeger UI at http://localhost:16686 to view traces.

### Trace Context Propagation

Traces automatically propagate across service boundaries through message queues. Each message includes trace context
(`trace_id` and `span_id`) in the `QueueMessageStats`, ensuring complete end-to-end tracing.

## Metrics Collection

LlamaDeployment includes Prometheus metrics for monitoring system performance and health.

### API Server Metrics

The API server automatically exposes Prometheus metrics when enabled:

```bash
# Enable Prometheus metrics (default: true)
export LLAMA_DEPLOY_APISERVER_PROMETHEUS_ENABLED=true

# Set metrics port (default: 9000)
export LLAMA_DEPLOY_APISERVER_PROMETHEUS_PORT=9000
```

Metrics are available at `http://localhost:9000/metrics`.

### Available Metrics

The API server tracks several key metrics:

- **Deployment State**: Current state of deployments (running, stopped, etc.)
- **Service State**: Health and status of registered services
- **API Request Metrics**: HTTP request counts, durations, and error rates (via tracing integration)

### Setting Up Prometheus

Create a `prometheus.yml` configuration file:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'llama-deploy-apiserver'
    static_configs:
      - targets: ['localhost:9000']
    scrape_interval: 5s
```

Run Prometheus:

```bash
# Using Docker
docker run -d --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Using binary
prometheus --config.file=prometheus.yml
```

Access Prometheus at http://localhost:9090.

### Setting Up Grafana

For advanced visualization, set up Grafana with Prometheus as a data source:

```bash
# Run Grafana
docker run -d --name grafana \
  -p 3000:3000 \
  grafana/grafana
```

1. Open http://localhost:3000 (admin/admin)
2. Add Prometheus as data source: http://localhost:9090
3. Create dashboards to visualize LlamaDeployment metrics

## Best Practices

### Sampling

For production deployments, configure appropriate sampling rates to balance observability with performance:

```bash
# Sample 10% of traces
export LLAMA_DEPLOY_APISERVER_TRACING_SAMPLE_RATE=0.1
```

### Service Names

Use descriptive service names to distinguish between different deployments:

```bash
export LLAMA_DEPLOY_APISERVER_TRACING_SERVICE_NAME=prod-rag-workflow
export LLAMA_DEPLOY_APISERVER_TRACING_SERVICE_NAME=prod-api-server
```

### Resource Attributes

Add custom resource attributes for better filtering:

```python
from llama_deploy.apiserver.tracing.utils import add_span_attribute

# Add custom attributes in your workflow
add_span_attribute("workflow.type", "rag")
add_span_attribute("environment", "production")
```

### Monitoring Alerts

Set up alerts based on metrics:

```yaml
# Prometheus alerting rule example
- alert: DeploymentDown
  expr: llama_deploy_deployment_state{state="stopped"} > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "LlamaDeployment deployment is down"
```

## Troubleshooting

### Traces Not Appearing

1. Verify tracing is enabled: `LLAMA_DEPLOY_APISERVER_TRACING_ENABLED=true`
2. Check exporter configuration and endpoint connectivity
3. Verify sampling rate is not too low
4. Check application logs for tracing errors

### Missing Dependencies

Install tracing dependencies:

```bash
pip install llama-deploy[observability]
```

### Performance Impact

- Tracing adds minimal overhead when properly configured
- Use sampling to reduce overhead in high-traffic scenarios
- Console exporter has higher overhead than Jaeger/OTLP

### Metrics Not Available

1. Verify Prometheus is enabled: `LLAMA_DEPLOY_APISERVER_PROMETHEUS_ENABLED=true`
2. Check metrics port is accessible: `curl http://localhost:9000/metrics`
3. Verify Prometheus configuration and targets

## Security Considerations

### Sensitive Data

Tracing doesn't automatically exclude sensitive parameters from span attributes. Review custom span attributes to
ensure no sensitive data is included.

### Network Security

When using OTLP in production:

```bash
# Use secure connections
export LLAMA_DEPLOY_APISERVER_TRACING_INSECURE=false
export LLAMA_DEPLOY_APISERVER_TRACING_ENDPOINT=https://your-secure-endpoint.com
```
