# DatabaseSlowQuery 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0313-db_slow_query`
- 数据类型: `aiops_alert_rule`
- 告警名称: `DatabaseSlowQuery`
- 告警分类: `数据库异常`
- 默认级别: `warning`

## 告警语义

慢查询数量 10 分钟内超过 100 条或单 SQL 超过 1 秒

## 适用场景

数据库 CPU 升高，接口响应慢，连接池等待时间变长。

## 推荐 PromQL 模板

- `mysql_global_status_slow_queries`
- `mysql_global_status_threads_connected`

## 推荐日志查询模板

- `query_time:>1000 OR slow_query:true`
- `full_table_scan:true OR rows_examined:>100000`

## 根因候选

- SQL 缺少索引或索引失效
- 业务参数导致全表扫描
- 热点表数据量增长后执行计划变化
- 慢查询集中在报表或批处理任务

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `DatabaseSlowQuery`、`数据库异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
