# cls-collector - KubernetesPodCrashLooping 运维处置知识

## 元数据

- 文档ID: `AIOPS-0119-pod_crash_loop-cls-collector`
- 数据类型: `aiops_runbook`
- 告警名称: `KubernetesPodCrashLooping`
- 告警分类: `容器异常`
- 告警级别: `critical`
- 服务名称: `cls-collector`
- 服务角色: `collector`
- 命名空间: `prod`
- 责任团队: `sre-team`
- 日志主题: `collector-logs`
- 指标 Job: `cls-collector`

## 触发条件

Pod 进入 CrashLoopBackOff 且 5 分钟内重启超过 3 次

## 症状描述

实例反复重启，服务副本不足，请求失败或消费中断。

## 推荐 PromQL

- `increase(kube_pod_container_status_restarts_total{pod=~"$pod"}[10m])`
- `kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}`

## 推荐日志查询

- `CrashLoopBackOff OR OOMKilled OR failed to start`
- `container exited OR readiness probe failed`

## 常见根因

- 启动参数或配置错误
- 依赖服务不可达导致启动失败
- 内存限制过小触发 OOMKilled
- 健康检查过严导致频繁重启

## 立即处置

1. 查看上一轮容器日志和退出码
2. 临时回滚到上一个稳定版本
3. 检查 ConfigMap、Secret 和环境变量
4. 必要时放宽健康检查或提高资源限制

## 诊断步骤

1. kubectl describe pod 查看事件
2. kubectl logs --previous 查看崩溃前日志
3. 核对镜像版本、启动命令和配置变更
4. 检查节点资源和依赖服务状态

## 验证标准

- Pod 进入 Running 且 ready
- 重启次数不再增加
- 服务 endpoints 恢复完整

## 预防措施

- 发布前增加启动检查和配置校验
- 为核心服务配置金丝雀发布
- 健康检查阈值与启动耗时匹配

## Agent 使用提示

当用户询问 `cls-collector` 的 `KubernetesPodCrashLooping`、`容器异常`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
