# kafka-broker - KubernetesNodeNotReady 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0206-node_not_ready-kafka-broker`
- 数据类型: `aiops_incident_case`
- 告警名称: `KubernetesNodeNotReady`
- 告警分类: `集群节点异常`
- 告警级别: `critical`
- 受影响服务: `kafka-broker`
- 命名空间: `prod`
- 责任团队: `platform-team`

## 事件摘要

`kafka-broker` 触发 `KubernetesNodeNotReady`，触发条件为：Kubernetes 节点 NotReady 超过 5 分钟。
用户侧表现为：节点上的 Pod 被驱逐或不可达，服务可用副本下降。

## 关键证据

### 指标证据

- 推荐查询: `kube_node_status_condition{condition="Ready",status!="true"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `NodeNotReady OR kubelet stopped posting node status`
- 日志主题: `kafka-logs`
- 证据模式: 日志中出现与 `KubernetesNodeNotReady` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：磁盘压力或内存压力触发节点异常

## 处置过程

1. 对异常节点 cordon/drain
2. 必要时重启 kubelet 或替换节点
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 服务可用副本数恢复
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
