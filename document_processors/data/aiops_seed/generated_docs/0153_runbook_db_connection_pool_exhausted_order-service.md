# order-service - DatabaseConnectionPoolExhausted 运维处置知识

## 元数据

- 文档ID: `AIOPS-0153-db_connection_pool_exhausted-order-service`
- 数据类型: `aiops_runbook`
- 告警名称: `DatabaseConnectionPoolExhausted`
- 告警分类: `数据库异常`
- 告警级别: `critical`
- 服务名称: `order-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `order-team`
- 日志主题: `application-logs`
- 指标 Job: `order-service`

## 触发条件

数据库连接池使用率连续 5 分钟超过 90% 或等待连接超时

## 症状描述

接口请求大量阻塞，应用线程等待数据库连接，P99 延迟和错误率同步升高。

## 推荐 PromQL

- `hikaricp_connections_active{service="$service"} / hikaricp_connections_max{service="$service"}`
- `rate(hikaricp_connections_timeout_total{service="$service"}[5m])`

## 推荐日志查询

- `connection pool exhausted OR timeout waiting for connection`
- `SQLTransientConnectionException OR too many connections`

## 常见根因

- 慢 SQL 长时间占用连接
- 连接泄漏导致连接未释放
- 连接池容量小于业务峰值需求
- 数据库 max_connections 配置过低

## 立即处置

1. 临时扩容应用实例或连接池上限
2. 限流高成本接口并保护核心写链路
3. 定位持有连接时间最长的 SQL
4. 必要时重启连接泄漏实例

## 诊断步骤

1. 查看连接池 active、idle、pending 趋势
2. 查询慢 SQL 和事务执行时间
3. 检查应用是否存在未关闭连接或事务
4. 确认数据库连接上限和当前连接数

## 验证标准

- 连接池等待数归零
- 连接超时错误消失
- 数据库连接数稳定在安全范围

## 预防措施

- 为数据库连接设置泄漏检测
- 治理慢 SQL 和长事务
- 连接池容量纳入压测基线

## Agent 使用提示

当用户询问 `order-service` 的 `DatabaseConnectionPoolExhausted`、`数据库异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
