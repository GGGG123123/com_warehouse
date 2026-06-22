# KubernetesPodPending 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0321-pod_pending`
- 数据类型: `aiops_alert_rule`
- 告警名称: `KubernetesPodPending`
- 告警分类: `容器调度异常`
- 默认级别: `warning`

## 告警语义

Pod 处于 Pending 状态超过 10 分钟

## 适用场景

新实例无法启动，扩容无效，服务副本数低于期望。

## 推荐 PromQL 模板

- `kube_pod_status_phase{phase="Pending",namespace="$namespace"}`
- `kube_pod_container_resource_requests{namespace="$namespace"}`

## 推荐日志查询模板

- `FailedScheduling OR Insufficient cpu OR Insufficient memory`
- `node affinity OR taint OR toleration`

## 根因候选

- 集群资源不足无法调度
- 节点污点、亲和性或反亲和性配置不匹配
- PVC 绑定失败
- 镜像拉取密钥或配额限制异常

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `KubernetesPodPending`、`容器调度异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
