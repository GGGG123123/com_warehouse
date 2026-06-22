# vector-indexer - KubernetesPodPending 运维处置知识

## 元数据

- 文档ID: `AIOPS-0185-pod_pending-vector-indexer`
- 数据类型: `aiops_runbook`
- 告警名称: `KubernetesPodPending`
- 告警分类: `容器调度异常`
- 告警级别: `warning`
- 服务名称: `vector-indexer`
- 服务角色: `worker`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `application-logs`
- 指标 Job: `vector-indexer`

## 触发条件

Pod 处于 Pending 状态超过 10 分钟

## 症状描述

新实例无法启动，扩容无效，服务副本数低于期望。

## 推荐 PromQL

- `kube_pod_status_phase{phase="Pending",namespace="$namespace"}`
- `kube_pod_container_resource_requests{namespace="$namespace"}`

## 推荐日志查询

- `FailedScheduling OR Insufficient cpu OR Insufficient memory`
- `node affinity OR taint OR toleration`

## 常见根因

- 集群资源不足无法调度
- 节点污点、亲和性或反亲和性配置不匹配
- PVC 绑定失败
- 镜像拉取密钥或配额限制异常

## 立即处置

1. 查看 pod describe 中的调度失败原因
2. 释放低优先级负载或扩容节点
3. 修正 nodeSelector、affinity、toleration
4. 检查 PVC 和 StorageClass 状态

## 诊断步骤

1. kubectl describe pod 查看 Events
2. 检查节点可用 CPU、内存和 Pod 配额
3. 检查 namespace ResourceQuota
4. 确认 PVC 是否 Bound

## 验证标准

- Pod 从 Pending 进入 Running
- Deployment 可用副本数达到期望
- 调度失败事件不再新增

## 预防措施

- 为核心服务预留资源池
- 建立节点容量和 Pending Pod 告警
- 发布前校验资源请求和调度约束

## Agent 使用提示

当用户询问 `vector-indexer` 的 `KubernetesPodPending`、`容器调度异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
