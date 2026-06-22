# CertificateExpiringSoon 告警规则与诊断提示

## 元数据

- 文档ID: `AIOPS-ALERT-RULE-0328-certificate_expiring`
- 数据类型: `aiops_alert_rule`
- 告警名称: `CertificateExpiringSoon`
- 告警分类: `安全与证书`
- 默认级别: `warning`

## 告警语义

TLS 证书将在 14 天内过期

## 适用场景

证书过期后 HTTPS 访问失败，客户端出现证书不可信错误。

## 推荐 PromQL 模板

- `probe_ssl_earliest_cert_expiry - time()`
- `ssl_certificate_expiry_seconds{domain="$domain"}`

## 推荐日志查询模板

- `certificate expired OR x509 OR TLS handshake failed`
- `cert-manager renewal failed OR secret not found`

## 根因候选

- 证书自动续期失败
- DNS 校验或 HTTP 校验失败
- 证书 Secret 未同步到 Ingress
- 证书链配置不完整

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `CertificateExpiringSoon`、`安全与证书`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
