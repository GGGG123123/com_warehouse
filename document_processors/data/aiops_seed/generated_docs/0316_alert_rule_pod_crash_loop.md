# KubernetesPodCrashLooping 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0316-pod_crash_loop`
- 数据类型: `aiops_alert_rule`
- 告警名称: `KubernetesPodCrashLooping`
- 告警分类: `容器异常`
- 默认级别: `critical`

## 告警语义

Pod 进入 CrashLoopBackOff 且 5 分钟内重启超过 3 次

## 适用场景

实例反复重启，服务副本不足，请求失败或消费中断。

## 推荐 PromQL 模板

- `increase(kube_pod_container_status_restarts_total{pod=~"$pod"}[10m])`
- `kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}`

## 推荐日志查询模板

- `CrashLoopBackOff OR OOMKilled OR failed to start`
- `container exited OR readiness probe failed`

## 根因候选

- 启动参数或配置错误
- 依赖服务不可达导致启动失败
- 内存限制过小触发 OOMKilled
- 健康检查过严导致频繁重启

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `KubernetesPodCrashLooping`、`容器异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
