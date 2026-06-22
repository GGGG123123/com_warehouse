# payment-service - HighErrorRate 运维处置知识

## 元数据

- 文档ID: `AIOPS-0061-high_error_rate-payment-service`
- 数据类型: `aiops_runbook`
- 告警名称: `HighErrorRate`
- 告警分类: `业务错误`
- 告警级别: `critical`
- 服务名称: `payment-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `payment-team`
- 日志主题: `application-logs`
- 指标 Job: `payment-service`

## 触发条件

5xx 错误率连续 5 分钟超过 5%

## 症状描述

接口返回 5xx 增多，用户操作失败，错误日志集中出现。

## 推荐 PromQL

- `sum(rate(http_requests_total{status=~"5..",service="$service"}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))`
- `sum(rate(exceptions_total{service="$service"}[5m])) by (exception)`

## 推荐日志查询

- `level:ERROR AND service:$service`
- `exception OR stacktrace OR panic OR traceback`

## 常见根因

- 新版本发布引入异常
- 配置错误导致依赖地址或密钥不可用
- 下游服务失败未做降级
- 数据库或缓存连接异常

## 立即处置

1. 确认是否和发布窗口重合，必要时回滚
2. 开启熔断降级，避免错误扩散
3. 检查配置中心和密钥有效性
4. 隔离异常实例并保留日志现场

## 诊断步骤

1. 按错误码、接口、实例聚合错误日志
2. 查看异常栈的首个业务错误位置
3. 对比错误开始时间和变更记录
4. 检查下游依赖状态和连接池指标

## 验证标准

- 5xx 错误率恢复到 1% 以下
- 异常日志数量下降到基线
- 核心交易链路恢复成功

## 预防措施

- 增加发布前冒烟测试
- 关键依赖增加健康检查和兜底
- 错误率告警按接口和版本维度细分

## Agent 使用提示

当用户询问 `payment-service` 的 `HighErrorRate`、`业务错误`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
