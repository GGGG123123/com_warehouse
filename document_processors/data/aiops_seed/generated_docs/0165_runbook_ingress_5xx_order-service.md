# order-service - Ingress5xxRateHigh 运维处置知识

## 元数据

- 文档ID: `AIOPS-0165-ingress_5xx-order-service`
- 数据类型: `aiops_runbook`
- 告警名称: `Ingress5xxRateHigh`
- 告警分类: `网关异常`
- 告警级别: `critical`
- 服务名称: `order-service`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `order-team`
- 日志主题: `application-logs`
- 指标 Job: `order-service`

## 触发条件

Ingress 5xx 比例连续 5 分钟超过 3%

## 症状描述

入口网关返回 502/503/504，用户无法访问服务或请求超时。

## 推荐 PromQL

- `sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m])) by (ingress)`
- `sum(rate(nginx_ingress_controller_request_duration_seconds_count[5m])) by (ingress)`

## 推荐日志查询

- `status:502 OR status:503 OR status:504`
- `upstream timed out OR no live upstreams`

## 常见根因

- 后端 Pod 不健康或 endpoints 为空
- 上游服务响应超时
- Ingress 配置或路由规则错误
- 网关资源不足导致连接排队

## 立即处置

1. 确认后端服务 endpoints 是否存在
2. 回滚最近的 Ingress 配置变更
3. 扩容网关或后端服务
4. 临时提高网关超时时间并观察

## 诊断步骤

1. 按 ingress、service、status 聚合 5xx
2. 查看 nginx ingress 错误日志
3. 检查 service endpoints 和 pod readiness
4. 对比配置变更和故障开始时间

## 验证标准

- 5xx 比例恢复到 0.5% 以下
- 入口请求成功率恢复
- 后端 endpoints 数量稳定

## 预防措施

- Ingress 配置变更加入校验和灰度
- 为 endpoints 为空增加独立告警
- 对上游超时建立分级看板

## Agent 使用提示

当用户询问 `order-service` 的 `Ingress5xxRateHigh`、`网关异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
