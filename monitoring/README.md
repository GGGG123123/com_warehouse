# Prometheus 本地监控配置

本目录用于让 Prometheus 采集 SuperBizAgent 的运行指标，并让 Agent 通过
`query_prometheus_alerts` 工具查询当前告警。

## 1. 启动主程序

先启动 FastAPI 主服务，确保 `/metrics` 可访问：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

项目的 `start-windows.bat` 也是启动在 `9900` 端口。
如果你改成其他端口，例如直接使用 `.env` 里的 `PORT=9901`，
需要同步修改 `monitoring/prometheus.yml` 里的 target。

浏览器打开：

```text
http://localhost:9900/metrics
```

能看到 `super_biz_agent_...` 开头的指标，就说明应用指标暴露成功。

## 2. 启动 Prometheus

在项目根目录执行：

```powershell
docker compose -f monitoring\prometheus-docker-compose.yml up -d
```

打开 Prometheus：

```text
http://localhost:9090
```

## 3. 检查抓取状态

打开：

```text
http://localhost:9090/targets
```

确认 `super-biz-agent` 是 `UP`。

如果是 `DOWN`，检查：

- FastAPI 是否运行在 `9900` 端口；
- `monitoring/prometheus.yml` 里的 target 是否正确；
- 如果不用 Docker Prometheus，而是 Windows 本地 Prometheus，target 应改成 `localhost:9900`。

## 4. 检查告警

打开：

```text
http://localhost:9090/alerts
```

告警规则在：

```text
monitoring/alert_rules.yml
```

## 5. Agent 如何使用

项目里的工具：

```text
app/tools/query_metrics_alerts.py
```

会请求：

```text
GET http://127.0.0.1:9090/api/v1/alerts
```

对应 `.env`：

```env
PROMETHEUS_BASE_URL=http://127.0.0.1:9090
PROMETHEUS_REQUEST_TIMEOUT=10.0
```

当用户问：

```text
当前系统有没有告警？
```

Agent 可以调用 `query_prometheus_alerts`，拿到 Prometheus 当前 firing / pending 告警。

## 6. 查询示例

Prometheus 页面里可以查询：

```promql
up{job="super-biz-agent"}
```

```promql
super_biz_agent_system_cpu_percent
```

```promql
super_biz_agent_system_memory_percent
```
