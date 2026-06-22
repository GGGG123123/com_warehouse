# order-service - DatabaseSlowQuery 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0076-db_slow_query-order-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `DatabaseSlowQuery`
- 告警分类: `数据库异常`
- 告警级别: `warning`
- 受影响服务: `order-service`
- 命名空间: `prod`
- 责任团队: `order-team`

## 事件摘要

`order-service` 触发 `DatabaseSlowQuery`，触发条件为：慢查询数量 10 分钟内超过 100 条或单 SQL 超过 1 秒。
用户侧表现为：数据库 CPU 升高，接口响应慢，连接池等待时间变长。

## 关键证据

### 指标证据

- 推荐查询: `mysql_global_status_slow_queries`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `query_time:>1000 OR slow_query:true`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `DatabaseSlowQuery` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：SQL 缺少索引或索引失效

## 处置过程

1. 定位最慢 SQL 和调用来源
2. 必要时临时添加索引或禁用重任务
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 数据库 CPU 和连接数恢复正常
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
