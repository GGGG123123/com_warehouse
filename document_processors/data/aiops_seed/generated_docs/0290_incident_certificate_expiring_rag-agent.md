# rag-agent - CertificateExpiringSoon 故障案例

## 元数据

- 文档ID: `AIOPS-INCIDENT-0290-certificate_expiring-rag-agent`
- 数据类型: `aiops_incident_case`
- 告警名称: `CertificateExpiringSoon`
- 告警分类: `安全与证书`
- 告警级别: `warning`
- 受影响服务: `rag-agent`
- 命名空间: `prod`
- 责任团队: `ai-team`

## 事件摘要

`rag-agent` 触发 `CertificateExpiringSoon`，触发条件为：TLS 证书将在 14 天内过期。
用户侧表现为：证书过期后 HTTPS 访问失败，客户端出现证书不可信错误。

## 关键证据

### 指标证据

- 推荐查询: `probe_ssl_earliest_cert_expiry - time()`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `certificate expired OR x509 OR TLS handshake failed`
- 日志主题: `application-logs`
- 证据模式: 日志中出现与 `CertificateExpiringSoon` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：证书 Secret 未同步到 Ingress

## 处置过程

1. 确认 DNS 解析和校验路径可访问
2. 更新 Ingress 引用的 Secret
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- 客户端无证书错误
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
