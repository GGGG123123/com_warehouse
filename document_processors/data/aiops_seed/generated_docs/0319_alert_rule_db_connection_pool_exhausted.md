# DatabaseConnectionPoolExhausted 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0319-db_connection_pool_exhausted`
- 数据类型: `aiops_alert_rule`
- 告警名称: `DatabaseConnectionPoolExhausted`
- 告警分类: `数据库异常`
- 默认级别: `critical`

## 告警语义

数据库连接池使用率连续 5 分钟超过 90% 或等待连接超时

## 适用场景

接口请求大量阻塞，应用线程等待数据库连接，P99 延迟和错误率同步升高。

## 推荐 PromQL 模板

- `hikaricp_connections_active{service="$service"} / hikaricp_connections_max{service="$service"}`
- `rate(hikaricp_connections_timeout_total{service="$service"}[5m])`

## 推荐日志查询模板

- `connection pool exhausted OR timeout waiting for connection`
- `SQLTransientConnectionException OR too many connections`

## 根因候选

- 慢 SQL 长时间占用连接
- 连接泄漏导致连接未释放
- 连接池容量小于业务峰值需求
- 数据库 max_connections 配置过低

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `DatabaseConnectionPoolExhausted`、`数据库异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
