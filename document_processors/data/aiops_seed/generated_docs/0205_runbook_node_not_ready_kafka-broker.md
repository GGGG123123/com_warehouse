# kafka-broker - KubernetesNodeNotReady 运维处置知识

## 元数据

- 文档ID: `AIOPS-0205-node_not_ready-kafka-broker`
- 数据类型: `aiops_runbook`
- 告警名称: `KubernetesNodeNotReady`
- 告警分类: `集群节点异常`
- 告警级别: `critical`
- 服务名称: `kafka-broker`
- 服务角色: `queue`
- 命名空间: `prod`
- 责任团队: `platform-team`
- 日志主题: `kafka-logs`
- 指标 Job: `kafka`

## 触发条件

Kubernetes 节点 NotReady 超过 5 分钟

## 症状描述

节点上的 Pod 被驱逐或不可达，服务可用副本下降。

## 推荐 PromQL

- `kube_node_status_condition{condition="Ready",status!="true"}`
- `node_load1{instance="$node"}`

## 推荐日志查询

- `NodeNotReady OR kubelet stopped posting node status`
- `network unavailable OR disk pressure OR memory pressure`

## 常见根因

- 节点 kubelet 异常或节点宕机
- 节点网络不可达
- 磁盘压力或内存压力触发节点异常
- 容器运行时异常

## 立即处置

1. 确认节点是否可 SSH 和 kubelet 状态
2. 将核心负载迁移到健康节点
3. 对异常节点 cordon/drain
4. 必要时重启 kubelet 或替换节点

## 诊断步骤

1. 查看 node describe 中 Conditions 和 Events
2. 检查 kubelet、containerd、网络插件日志
3. 查看节点 CPU、内存、磁盘和网络指标
4. 确认同机房或同可用区是否有批量异常

## 验证标准

- 节点 Ready 状态恢复
- Pod 重新调度完成
- 服务可用副本数恢复

## 预防措施

- 为节点系统组件增加健康巡检
- 核心服务跨节点和跨可用区分布
- 对节点压力类指标提前预警

## Agent 使用提示

当用户询问 `kafka-broker` 的 `KubernetesNodeNotReady`、`集群节点异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
