# payment-service - DatabaseSlowQuery 运维处置知识

## 元数据

- 文档ID: `AIOPS-0077-db_slow_query-payment-service`
- 数据类型: `aiops_runbook`
- 告警名称: `DatabaseSlowQuery`
- 告警分类: `数据库异常`
- 告警级别: `warning`
- 服务名称: `payment-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `payment-team`
- 日志主题: `application-logs`
- 指标 Job: `payment-service`

## 触发条件

慢查询数量 10 分钟内超过 100 条或单 SQL 超过 1 秒

## 症状描述

数据库 CPU 升高，接口响应慢，连接池等待时间变长。

## 推荐 PromQL

- `mysql_global_status_slow_queries`
- `mysql_global_status_threads_connected`

## 推荐日志查询

- `query_time:>1000 OR slow_query:true`
- `full_table_scan:true OR rows_examined:>100000`

## 常见根因

- SQL 缺少索引或索引失效
- 业务参数导致全表扫描
- 热点表数据量增长后执行计划变化
- 慢查询集中在报表或批处理任务

## 立即处置

1. 定位最慢 SQL 和调用来源
2. 必要时临时添加索引或禁用重任务
3. 限制高成本查询并保护核心链路
4. 增加只读副本承担读查询

## 诊断步骤

1. 查询慢查询日志 TopN
2. 执行 EXPLAIN 检查索引和扫描行数
3. 查看连接池等待和数据库 CPU 趋势
4. 确认是否存在报表导出或批量任务

## 验证标准

- 慢查询数量回落
- 数据库 CPU 和连接数恢复正常
- 接口延迟恢复到基线

## 预防措施

- 建立 SQL 审核和索引评审
- 对大表查询增加分页和条件限制
- 定期归档冷数据并更新统计信息

## Agent 使用提示

当用户询问 `payment-service` 的 `DatabaseSlowQuery`、`数据库异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
