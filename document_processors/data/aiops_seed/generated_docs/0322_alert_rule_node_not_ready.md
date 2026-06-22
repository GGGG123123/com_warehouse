# KubernetesNodeNotReady 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0322-node_not_ready`
- 数据类型: `aiops_alert_rule`
- 告警名称: `KubernetesNodeNotReady`
- 告警分类: `集群节点异常`
- 默认级别: `critical`

## 告警语义

Kubernetes 节点 NotReady 超过 5 分钟

## 适用场景

节点上的 Pod 被驱逐或不可达，服务可用副本下降。

## 推荐 PromQL 模板

- `kube_node_status_condition{condition="Ready",status!="true"}`
- `node_load1{instance="$node"}`

## 推荐日志查询模板

- `NodeNotReady OR kubelet stopped posting node status`
- `network unavailable OR disk pressure OR memory pressure`

## 根因候选

- 节点 kubelet 异常或节点宕机
- 节点网络不可达
- 磁盘压力或内存压力触发节点异常
- 容器运行时异常

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `KubernetesNodeNotReady`、`集群节点异常`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
