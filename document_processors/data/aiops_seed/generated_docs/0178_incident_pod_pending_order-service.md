# order-service - KubernetesPodPending 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0178-pod_pending-order-service`
- 数据类型: `aiops_incident_case`
- 告警名称: `KubernetesPodPending`
- 告警分类: `容器调度异常`
- 告警级别: `warning`
- 受影响服务: `order-service`
- 命名空间: `prod`
- 责任团队: `order-team`

## 事件摘要

`order-service` 触发 `KubernetesPodPending`，触发条件为：Pod 处于 Pending 状态超过 10 分钟。
用户侧表现为：新实例无法启动，扩容无效，服务副本数低于期望。

## 关键证据

### 指标证据

- 推荐查询: `kube_pod_status_phase{phase="Pending",namespace="$namespace"}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `FailedScheduling OR Insufficient cpu OR Insufficient memory`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `KubernetesPodPending` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：PVC 绑定失败

## 处置过程

1. 修正 nodeSelector、affinity、toleration
2. 检查 PVC 和 StorageClass 状态
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- Deployment 可用副本数达到期望
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
