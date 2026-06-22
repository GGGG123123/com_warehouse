# nginx-ingress - KubernetesPodCrashLooping 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0118-pod_crash_loop-nginx-ingress`
- 数据类型: `aiops_incident_case`
- 告警名称: `KubernetesPodCrashLooping`
- 告警分类: `容器异常`
- 告警级别: `critical`
- 受影响服务: `nginx-ingress`
- 命名空间: `prod`
- 责任团队: `platform-team`

## 事件摘要

`nginx-ingress` 触发 `KubernetesPodCrashLooping`，触发条件为：Pod 进入 CrashLoopBackOff 且 5 分钟内重启超过 3 次。
用户侧表现为：实例反复重启，服务副本不足，请求失败或消费中断。

## 关键证据

### 指标证据

- 推荐查询: `increase(kube_pod_container_status_restarts_total{pod=~"$pod"}[10m])`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `CrashLoopBackOff OR OOMKilled OR failed to start`
- 日志主题: `ingress-logs`
- 证据模式: 日志中出现与 `KubernetesPodCrashLooping` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：内存限制过小触发 OOMKilled

## 处置过程

1. 检查 ConfigMap、Secret 和环境变量
2. 必要时放宽健康检查或提高资源限制
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 重启次数不再增加
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
