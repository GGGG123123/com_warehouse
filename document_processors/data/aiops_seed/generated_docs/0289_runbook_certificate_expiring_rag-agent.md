# rag-agent - CertificateExpiringSoon 运维处置知识

## 元数据

- 文档ID: `AIOPS-0289-certificate_expiring-rag-agent`
- 数据类型: `aiops_runbook`
- 告警名称: `CertificateExpiringSoon`
- 告警分类: `安全与证书`
- 告警级别: `warning`
- 服务名称: `rag-agent`
- 服务角色: `app`
- 命名空间: `prod`
- 责任团队: `ai-team`
- 日志主题: `application-logs`
- 指标 Job: `rag-agent`

## 触发条件

TLS 证书将在 14 天内过期

## 症状描述

证书过期后 HTTPS 访问失败，客户端出现证书不可信错误。

## 推荐 PromQL

- `probe_ssl_earliest_cert_expiry - time()`
- `ssl_certificate_expiry_seconds{domain="$domain"}`

## 推荐日志查询

- `certificate expired OR x509 OR TLS handshake failed`
- `cert-manager renewal failed OR secret not found`

## 常见根因

- 证书自动续期失败
- DNS 校验或 HTTP 校验失败
- 证书 Secret 未同步到 Ingress
- 证书链配置不完整

## 立即处置

1. 手动触发证书续期
2. 检查 cert-manager challenge 状态
3. 确认 DNS 解析和校验路径可访问
4. 更新 Ingress 引用的 Secret

## 诊断步骤

1. 查看证书剩余有效期
2. 检查 Certificate、Order、Challenge 资源
3. 查看 cert-manager 日志
4. 验证域名证书链是否完整

## 验证标准

- 新证书有效期更新
- HTTPS 握手正常
- 客户端无证书错误

## 预防措施

- 证书过期提前 30/14/7 天多级告警
- 续期失败告警直接通知值班
- 证书 Secret 同步纳入发布检查

## Agent 使用提示

当用户询问 `rag-agent` 的 `CertificateExpiringSoon`、`安全与证书`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
