# api-gateway - DatabaseConnectionPoolExhausted 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0152-db_connection_pool_exhausted-api-gateway`
- 数据类型: `aiops_incident_case`
- 告警名称: `DatabaseConnectionPoolExhausted`
- 告警分类: `数据库异常`
- 告警级别: `critical`
- 受影响服务: `api-gateway`
- 命名空间: `prod`
- 责任团队: `platform-team`

## 事件摘要

`api-gateway` 触发 `DatabaseConnectionPoolExhausted`，触发条件为：数据库连接池使用率连续 5 分钟超过 90% 或等待连接超时。
用户侧表现为：接口请求大量阻塞，应用线程等待数据库连接，P99 延迟和错误率同步升高。

## 关键证据

### 指标证据

- 推荐查询: `hikaricp_connections_active{service="$service"} / hikaricp_connections_max{service="$service"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `connection pool exhausted OR timeout waiting for connection`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `DatabaseConnectionPoolExhausted` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：慢 SQL 长时间占用连接

## 处置过程

1. 临时扩容应用实例或连接池上限
2. 限流高成本接口并保护核心写链路
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 数据库连接数稳定在安全范围
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
