"""生成 AIOps 运维知识库种子数据。

这个脚本根据当前项目的目标生成可入库的运维数据:

- Markdown 文档: 适合现有 `vector_index_service.index_directory()` 直接入 Milvus 向量库；
- JSONL 数据: 保留结构化字段，适合后续落关系数据库、对象库或调试。

运行:
    python scripts/generate_aiops_seed_data.py

生成位置:
    data/aiops_seed/generated_docs/*.md
    data/aiops_seed/aiops_seed_records.jsonl
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

OUTPUT_DOCS_DIR = Path("data/aiops_seed/generated_docs")
OUTPUT_JSONL_PATH = Path("data/aiops_seed/aiops_seed_records.jsonl")


@dataclass(frozen=True)
class ServiceProfile:
    """服务画像，用于生成有业务语境的运维数据。"""

    name: str
    role: str
    namespace: str
    owner: str
    log_topic: str
    metrics_job: str


@dataclass(frozen=True)
class ScenarioTemplate:
    """运维场景模板。"""

    code: str
    alert_name: str
    category: str
    severity: str
    service_roles: tuple[str, ...]
    trigger: str
    symptom: str
    metric_queries: tuple[str, ...]
    log_queries: tuple[str, ...]
    root_causes: tuple[str, ...]
    immediate_actions: tuple[str, ...]
    diagnosis_steps: tuple[str, ...]
    verification: tuple[str, ...]
    prevention: tuple[str, ...]


SERVICES = [
    ServiceProfile("api-gateway", "app", "prod", "platform-team", "application-logs", "api-gateway"),
    ServiceProfile("order-service", "app", "prod", "order-team", "application-logs", "order-service"),
    ServiceProfile("payment-service", "app", "prod", "payment-team", "application-logs", "payment-service"),
    ServiceProfile("user-service", "app", "prod", "user-team", "application-logs", "user-service"),
    ServiceProfile("rag-agent", "app", "prod", "ai-team", "application-logs", "rag-agent"),
    ServiceProfile("vector-indexer", "worker", "prod", "ai-team", "application-logs", "vector-indexer"),
    ServiceProfile("embedding-worker", "worker", "prod", "ai-team", "application-logs", "embedding-worker"),
    ServiceProfile("mysql-primary", "db", "prod", "dba-team", "database-logs", "mysql"),
    ServiceProfile("redis-cluster", "cache", "prod", "platform-team", "redis-logs", "redis"),
    ServiceProfile("milvus-vector-db", "vector_db", "prod", "ai-team", "milvus-logs", "milvus"),
    ServiceProfile("kafka-broker", "queue", "prod", "platform-team", "kafka-logs", "kafka"),
    ServiceProfile("nginx-ingress", "gateway", "prod", "platform-team", "ingress-logs", "nginx-ingress"),
    ServiceProfile("prometheus", "monitor", "monitoring", "sre-team", "monitoring-logs", "prometheus"),
    ServiceProfile("cls-collector", "collector", "prod", "sre-team", "collector-logs", "cls-collector"),
]


SCENARIOS = [
    ScenarioTemplate(
        code="high_cpu",
        alert_name="HighCPUUsage",
        category="资源异常",
        severity="critical",
        service_roles=("app", "worker", "gateway", "db", "vector_db"),
        trigger="CPU 使用率连续 5 分钟超过 85%",
        symptom="实例负载升高、接口响应变慢、请求排队增加，严重时出现超时。",
        metric_queries=(
            'avg(rate(container_cpu_usage_seconds_total{pod=~"$pod"}[5m])) by (pod)',
            'node_load1{instance="$instance"}',
        ),
        log_queries=(
            'level:ERROR OR cpu_usage:>85',
            'thread_pool_queue_size:>100 OR slow_request:true',
        ),
        root_causes=(
            "流量突增导致业务线程持续满载",
            "代码死循环或热点方法 CPU 消耗异常",
            "慢 SQL 或外部接口阻塞导致请求堆积",
            "定时任务和在线流量重叠执行",
        ),
        immediate_actions=(
            "确认是否单实例异常，必要时摘除异常实例",
            "如果整体流量上涨，优先水平扩容",
            "开启限流或降级非核心接口",
            "保留线程栈和关键日志后再重启",
        ),
        diagnosis_steps=(
            "查询最近 30 分钟 CPU、QPS、P99 延迟变化趋势",
            "查询同时间窗口应用错误日志和慢请求日志",
            "检查线程池、连接池和下游依赖耗时",
            "对比发布记录、定时任务和流量入口变化",
        ),
        verification=(
            "CPU 使用率回落到 60% 以下",
            "P99 延迟恢复到基线范围",
            "错误率和超时数量不再增长",
        ),
        prevention=(
            "为热点接口增加限流和熔断",
            "补充 CPU 火焰图和线程池队列监控",
            "将重任务迁移到异步队列或离峰执行",
        ),
    ),
    ScenarioTemplate(
        code="high_memory",
        alert_name="HighMemoryUsage",
        category="资源异常",
        severity="critical",
        service_roles=("app", "worker", "db", "vector_db"),
        trigger="内存使用率连续 5 分钟超过 85%",
        symptom="内存持续上涨、GC 频繁、实例重启、可能触发 OOMKilled。",
        metric_queries=(
            'container_memory_working_set_bytes{pod=~"$pod"}',
            'increase(container_oom_events_total{pod=~"$pod"}[30m])',
        ),
        log_queries=(
            'OutOfMemoryError OR OOMKilled OR memory_usage:>85',
            'Full GC OR GC overhead OR heap dump',
        ),
        root_causes=(
            "内存泄漏导致 Full GC 后无法回收",
            "缓存容量或 TTL 配置不合理",
            "批处理任务一次性加载大对象",
            "实例规格过小或堆内存参数配置不合理",
        ),
        immediate_actions=(
            "优先扩容或重启异常实例恢复服务",
            "重启前保留 heap dump 或内存快照",
            "降低缓存容量或临时清理热点缓存",
            "暂停大批量导入或离线任务",
        ),
        diagnosis_steps=(
            "查看内存趋势是否持续单调上涨",
            "检查 OOM 事件、GC 次数和 GC 耗时",
            "定位最近发布是否引入大对象或缓存变更",
            "分析 heap dump 中占用最高的对象类型",
        ),
        verification=(
            "内存使用率稳定低于 70%",
            "Full GC 频率恢复正常",
            "无新的 OOMKilled 或 OutOfMemoryError",
        ),
        prevention=(
            "对缓存设置容量上限和淘汰策略",
            "大文件处理改为流式或分批",
            "上线前做内存压测和泄漏检查",
        ),
    ),
    ScenarioTemplate(
        code="slow_response",
        alert_name="SlowResponse",
        category="性能异常",
        severity="warning",
        service_roles=("app", "gateway", "db", "cache", "vector_db"),
        trigger="P99 响应时间连续 5 分钟超过 3 秒",
        symptom="用户请求明显变慢，部分请求超时，下游调用耗时升高。",
        metric_queries=(
            'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))',
            'sum(rate(http_requests_total{service="$service",status=~"5.."}[5m]))',
        ),
        log_queries=(
            'response_time:>3000 OR timeout:true',
            'slow_query:true OR upstream_timeout:true',
        ),
        root_causes=(
            "数据库慢查询或缺少索引",
            "下游接口响应慢或超时",
            "缓存命中率下降导致数据库压力上升",
            "线程池耗尽或连接池耗尽",
        ),
        immediate_actions=(
            "启用降级策略保护核心链路",
            "临时扩容慢服务实例",
            "对热点接口启用缓存或提高缓存 TTL",
            "对异常下游启用熔断和超时控制",
        ),
        diagnosis_steps=(
            "按接口维度查看 P95/P99 和错误率",
            "查询慢 SQL、下游调用耗时和超时日志",
            "检查缓存命中率、连接池和线程池指标",
            "确认是否有发布、配置或流量变化",
        ),
        verification=(
            "P99 延迟低于 1 秒或恢复到业务基线",
            "超时错误数量不再增长",
            "核心链路成功率恢复正常",
        ),
        prevention=(
            "建立慢接口 TopN 看板",
            "为外部依赖设置合理超时、重试和熔断",
            "上线前执行容量评估和压测",
        ),
    ),
    ScenarioTemplate(
        code="high_error_rate",
        alert_name="HighErrorRate",
        category="业务错误",
        severity="critical",
        service_roles=("app", "gateway", "worker"),
        trigger="5xx 错误率连续 5 分钟超过 5%",
        symptom="接口返回 5xx 增多，用户操作失败，错误日志集中出现。",
        metric_queries=(
            'sum(rate(http_requests_total{status=~"5..",service="$service"}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))',
            'sum(rate(exceptions_total{service="$service"}[5m])) by (exception)',
        ),
        log_queries=(
            'level:ERROR AND service:$service',
            'exception OR stacktrace OR panic OR traceback',
        ),
        root_causes=(
            "新版本发布引入异常",
            "配置错误导致依赖地址或密钥不可用",
            "下游服务失败未做降级",
            "数据库或缓存连接异常",
        ),
        immediate_actions=(
            "确认是否和发布窗口重合，必要时回滚",
            "开启熔断降级，避免错误扩散",
            "检查配置中心和密钥有效性",
            "隔离异常实例并保留日志现场",
        ),
        diagnosis_steps=(
            "按错误码、接口、实例聚合错误日志",
            "查看异常栈的首个业务错误位置",
            "对比错误开始时间和变更记录",
            "检查下游依赖状态和连接池指标",
        ),
        verification=(
            "5xx 错误率恢复到 1% 以下",
            "异常日志数量下降到基线",
            "核心交易链路恢复成功",
        ),
        prevention=(
            "增加发布前冒烟测试",
            "关键依赖增加健康检查和兜底",
            "错误率告警按接口和版本维度细分",
        ),
    ),
    ScenarioTemplate(
        code="db_slow_query",
        alert_name="DatabaseSlowQuery",
        category="数据库异常",
        severity="warning",
        service_roles=("db", "app"),
        trigger="慢查询数量 10 分钟内超过 100 条或单 SQL 超过 1 秒",
        symptom="数据库 CPU 升高，接口响应慢，连接池等待时间变长。",
        metric_queries=(
            'mysql_global_status_slow_queries',
            'mysql_global_status_threads_connected',
        ),
        log_queries=(
            'query_time:>1000 OR slow_query:true',
            'full_table_scan:true OR rows_examined:>100000',
        ),
        root_causes=(
            "SQL 缺少索引或索引失效",
            "业务参数导致全表扫描",
            "热点表数据量增长后执行计划变化",
            "慢查询集中在报表或批处理任务",
        ),
        immediate_actions=(
            "定位最慢 SQL 和调用来源",
            "必要时临时添加索引或禁用重任务",
            "限制高成本查询并保护核心链路",
            "增加只读副本承担读查询",
        ),
        diagnosis_steps=(
            "查询慢查询日志 TopN",
            "执行 EXPLAIN 检查索引和扫描行数",
            "查看连接池等待和数据库 CPU 趋势",
            "确认是否存在报表导出或批量任务",
        ),
        verification=(
            "慢查询数量回落",
            "数据库 CPU 和连接数恢复正常",
            "接口延迟恢复到基线",
        ),
        prevention=(
            "建立 SQL 审核和索引评审",
            "对大表查询增加分页和条件限制",
            "定期归档冷数据并更新统计信息",
        ),
    ),
    ScenarioTemplate(
        code="redis_hit_rate_low",
        alert_name="RedisHitRateLow",
        category="缓存异常",
        severity="warning",
        service_roles=("cache", "app"),
        trigger="Redis 命中率连续 10 分钟低于 80%",
        symptom="数据库查询量上升，接口延迟增加，缓存 miss 日志增多。",
        metric_queries=(
            'redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)',
            'rate(redis_commands_processed_total[5m])',
        ),
        log_queries=(
            'cache_miss:true OR cache_penetration:true',
            'redis timeout OR redis connection refused',
        ),
        root_causes=(
            "缓存批量过期导致击穿",
            "缓存 key 设计不合理或版本变化",
            "热点数据未预热",
            "恶意或异常参数造成缓存穿透",
        ),
        immediate_actions=(
            "预热热点 key 并延长 TTL",
            "对空值结果设置短 TTL 缓存",
            "启用布隆过滤器或参数校验",
            "必要时限流保护数据库",
        ),
        diagnosis_steps=(
            "查看命中率、miss 数、数据库 QPS 同步变化",
            "按 key 前缀统计 miss TopN",
            "检查发布后 key 规则是否变更",
            "确认热点 key 是否同时过期",
        ),
        verification=(
            "缓存命中率恢复到 90% 以上",
            "数据库 QPS 回落到正常水平",
            "接口 P99 延迟恢复",
        ),
        prevention=(
            "TTL 增加随机抖动",
            "热点数据发布前预热",
            "缓存 key 规则纳入兼容性测试",
        ),
    ),
    ScenarioTemplate(
        code="queue_lag",
        alert_name="KafkaConsumerLagHigh",
        category="消息队列异常",
        severity="critical",
        service_roles=("queue", "worker"),
        trigger="消费者 lag 连续 10 分钟增长且超过 10000",
        symptom="异步任务积压，业务状态更新延迟，用户看到数据不同步。",
        metric_queries=(
            'kafka_consumergroup_lag{consumer_group="$group"}',
            'sum(rate(kafka_topic_partition_current_offset[5m])) by (topic)',
        ),
        log_queries=(
            'consumer lag OR rebalance OR poll timeout',
            'message_process_error OR retry_exhausted',
        ),
        root_causes=(
            "消费端处理能力不足",
            "消息处理失败后反复重试",
            "消费者频繁 rebalance",
            "单分区热点导致并行度不足",
        ),
        immediate_actions=(
            "扩容消费者实例或提高并发",
            "暂停异常消息并转入死信队列",
            "临时提高批量消费大小",
            "检查下游依赖，避免消费者阻塞",
        ),
        diagnosis_steps=(
            "查看 lag 增长速度和 topic 分区分布",
            "查询消费失败日志和重试次数",
            "检查消费者实例是否频繁重启",
            "确认下游数据库或外部 API 是否变慢",
        ),
        verification=(
            "consumer lag 持续下降",
            "死信队列无新增异常消息",
            "业务异步状态延迟恢复正常",
        ),
        prevention=(
            "为消费者配置死信队列和限次重试",
            "按 topic 分区评估并行度",
            "对耗时任务拆分或异步化",
        ),
    ),
    ScenarioTemplate(
        code="pod_crash_loop",
        alert_name="KubernetesPodCrashLooping",
        category="容器异常",
        severity="critical",
        service_roles=("app", "worker", "gateway", "collector"),
        trigger="Pod 进入 CrashLoopBackOff 且 5 分钟内重启超过 3 次",
        symptom="实例反复重启，服务副本不足，请求失败或消费中断。",
        metric_queries=(
            'increase(kube_pod_container_status_restarts_total{pod=~"$pod"}[10m])',
            'kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}',
        ),
        log_queries=(
            'CrashLoopBackOff OR OOMKilled OR failed to start',
            'container exited OR readiness probe failed',
        ),
        root_causes=(
            "启动参数或配置错误",
            "依赖服务不可达导致启动失败",
            "内存限制过小触发 OOMKilled",
            "健康检查过严导致频繁重启",
        ),
        immediate_actions=(
            "查看上一轮容器日志和退出码",
            "临时回滚到上一个稳定版本",
            "检查 ConfigMap、Secret 和环境变量",
            "必要时放宽健康检查或提高资源限制",
        ),
        diagnosis_steps=(
            "kubectl describe pod 查看事件",
            "kubectl logs --previous 查看崩溃前日志",
            "核对镜像版本、启动命令和配置变更",
            "检查节点资源和依赖服务状态",
        ),
        verification=(
            "Pod 进入 Running 且 ready",
            "重启次数不再增加",
            "服务 endpoints 恢复完整",
        ),
        prevention=(
            "发布前增加启动检查和配置校验",
            "为核心服务配置金丝雀发布",
            "健康检查阈值与启动耗时匹配",
        ),
    ),
    ScenarioTemplate(
        code="disk_full",
        alert_name="DiskSpaceLow",
        category="存储异常",
        severity="critical",
        service_roles=("app", "db", "vector_db", "queue", "monitor"),
        trigger="磁盘使用率连续 10 分钟超过 90%",
        symptom="日志无法写入、数据库写入失败、服务可能进入只读或崩溃。",
        metric_queries=(
            'node_filesystem_avail_bytes{mountpoint="/"}',
            '100 - node_filesystem_avail_bytes / node_filesystem_size_bytes * 100',
        ),
        log_queries=(
            'No space left on device OR disk full',
            'log rotate failed OR write failed',
        ),
        root_causes=(
            "日志滚动或清理策略失效",
            "临时文件、导出文件或 dump 文件堆积",
            "数据库 binlog、WAL 或 segment 文件增长",
            "监控采集异常导致本地缓存堆积",
        ),
        immediate_actions=(
            "清理可安全删除的临时文件和过期日志",
            "压缩或转移大文件",
            "扩大磁盘或挂载新卷",
            "暂停产生大量文件的任务",
        ),
        diagnosis_steps=(
            "du -xh --max-depth=1 定位大目录",
            "检查日志滚动配置和保留天数",
            "查看数据库日志、binlog、WAL 增长情况",
            "确认是否有异常 dump 或导出任务",
        ),
        verification=(
            "磁盘使用率低于 75%",
            "服务写入日志和数据恢复正常",
            "无新的 disk full 错误",
        ),
        prevention=(
            "配置日志轮转和保留策略",
            "为关键目录设置独立磁盘告警",
            "建立大文件巡检和自动清理任务",
        ),
    ),
    ScenarioTemplate(
        code="milvus_search_slow",
        alert_name="MilvusSearchLatencyHigh",
        category="向量数据库异常",
        severity="warning",
        service_roles=("vector_db", "app"),
        trigger="Milvus 向量检索 P95 延迟连续 10 分钟超过 1 秒",
        symptom="知识检索变慢，RAG 回答等待时间增加，部分查询超时。",
        metric_queries=(
            'histogram_quantile(0.95, sum(rate(milvus_proxy_search_latency_bucket[5m])) by (le))',
            'sum(rate(milvus_querynode_search_total[5m])) by (status)',
        ),
        log_queries=(
            'search timeout OR querynode overloaded',
            'collection not loaded OR index not found',
        ),
        root_causes=(
            "collection 未完全 load 或分片分布不均",
            "索引参数不合理导致召回代价高",
            "QueryNode 资源不足",
            "批量导入和查询同时进行造成资源争用",
        ),
        immediate_actions=(
            "确认 collection load 状态",
            "降低 top_k 或调整 nprobe 等搜索参数",
            "扩容 QueryNode 或隔离导入任务",
            "对低优先级查询做限流",
        ),
        diagnosis_steps=(
            "检查 Milvus Proxy 和 QueryNode 日志",
            "查看 collection、segment、index 状态",
            "分析查询 top_k、过滤条件和并发量",
            "对比导入任务和搜索延迟时间线",
        ),
        verification=(
            "搜索 P95 延迟恢复到 500ms 以下",
            "查询超时错误消失",
            "RAG 回答整体耗时恢复",
        ),
        prevention=(
            "导入和查询错峰",
            "为 collection 建立索引状态巡检",
            "按业务使用场景调优 top_k 和搜索参数",
        ),
    ),
    ScenarioTemplate(
        code="db_connection_pool_exhausted",
        alert_name="DatabaseConnectionPoolExhausted",
        category="数据库异常",
        severity="critical",
        service_roles=("app", "db"),
        trigger="数据库连接池使用率连续 5 分钟超过 90% 或等待连接超时",
        symptom="接口请求大量阻塞，应用线程等待数据库连接，P99 延迟和错误率同步升高。",
        metric_queries=(
            'hikaricp_connections_active{service="$service"} / hikaricp_connections_max{service="$service"}',
            'rate(hikaricp_connections_timeout_total{service="$service"}[5m])',
        ),
        log_queries=(
            'connection pool exhausted OR timeout waiting for connection',
            'SQLTransientConnectionException OR too many connections',
        ),
        root_causes=(
            "慢 SQL 长时间占用连接",
            "连接泄漏导致连接未释放",
            "连接池容量小于业务峰值需求",
            "数据库 max_connections 配置过低",
        ),
        immediate_actions=(
            "临时扩容应用实例或连接池上限",
            "限流高成本接口并保护核心写链路",
            "定位持有连接时间最长的 SQL",
            "必要时重启连接泄漏实例",
        ),
        diagnosis_steps=(
            "查看连接池 active、idle、pending 趋势",
            "查询慢 SQL 和事务执行时间",
            "检查应用是否存在未关闭连接或事务",
            "确认数据库连接上限和当前连接数",
        ),
        verification=(
            "连接池等待数归零",
            "连接超时错误消失",
            "数据库连接数稳定在安全范围",
        ),
        prevention=(
            "为数据库连接设置泄漏检测",
            "治理慢 SQL 和长事务",
            "连接池容量纳入压测基线",
        ),
    ),
    ScenarioTemplate(
        code="ingress_5xx",
        alert_name="Ingress5xxRateHigh",
        category="网关异常",
        severity="critical",
        service_roles=("gateway", "app"),
        trigger="Ingress 5xx 比例连续 5 分钟超过 3%",
        symptom="入口网关返回 502/503/504，用户无法访问服务或请求超时。",
        metric_queries=(
            'sum(rate(nginx_ingress_controller_requests{status=~"5.."}[5m])) by (ingress)',
            'sum(rate(nginx_ingress_controller_request_duration_seconds_count[5m])) by (ingress)',
        ),
        log_queries=(
            'status:502 OR status:503 OR status:504',
            'upstream timed out OR no live upstreams',
        ),
        root_causes=(
            "后端 Pod 不健康或 endpoints 为空",
            "上游服务响应超时",
            "Ingress 配置或路由规则错误",
            "网关资源不足导致连接排队",
        ),
        immediate_actions=(
            "确认后端服务 endpoints 是否存在",
            "回滚最近的 Ingress 配置变更",
            "扩容网关或后端服务",
            "临时提高网关超时时间并观察",
        ),
        diagnosis_steps=(
            "按 ingress、service、status 聚合 5xx",
            "查看 nginx ingress 错误日志",
            "检查 service endpoints 和 pod readiness",
            "对比配置变更和故障开始时间",
        ),
        verification=(
            "5xx 比例恢复到 0.5% 以下",
            "入口请求成功率恢复",
            "后端 endpoints 数量稳定",
        ),
        prevention=(
            "Ingress 配置变更加入校验和灰度",
            "为 endpoints 为空增加独立告警",
            "对上游超时建立分级看板",
        ),
    ),
    ScenarioTemplate(
        code="pod_pending",
        alert_name="KubernetesPodPending",
        category="容器调度异常",
        severity="warning",
        service_roles=("app", "worker", "collector"),
        trigger="Pod 处于 Pending 状态超过 10 分钟",
        symptom="新实例无法启动，扩容无效，服务副本数低于期望。",
        metric_queries=(
            'kube_pod_status_phase{phase="Pending",namespace="$namespace"}',
            'kube_pod_container_resource_requests{namespace="$namespace"}',
        ),
        log_queries=(
            'FailedScheduling OR Insufficient cpu OR Insufficient memory',
            'node affinity OR taint OR toleration',
        ),
        root_causes=(
            "集群资源不足无法调度",
            "节点污点、亲和性或反亲和性配置不匹配",
            "PVC 绑定失败",
            "镜像拉取密钥或配额限制异常",
        ),
        immediate_actions=(
            "查看 pod describe 中的调度失败原因",
            "释放低优先级负载或扩容节点",
            "修正 nodeSelector、affinity、toleration",
            "检查 PVC 和 StorageClass 状态",
        ),
        diagnosis_steps=(
            "kubectl describe pod 查看 Events",
            "检查节点可用 CPU、内存和 Pod 配额",
            "检查 namespace ResourceQuota",
            "确认 PVC 是否 Bound",
        ),
        verification=(
            "Pod 从 Pending 进入 Running",
            "Deployment 可用副本数达到期望",
            "调度失败事件不再新增",
        ),
        prevention=(
            "为核心服务预留资源池",
            "建立节点容量和 Pending Pod 告警",
            "发布前校验资源请求和调度约束",
        ),
    ),
    ScenarioTemplate(
        code="node_not_ready",
        alert_name="KubernetesNodeNotReady",
        category="集群节点异常",
        severity="critical",
        service_roles=("app", "worker", "gateway", "queue"),
        trigger="Kubernetes 节点 NotReady 超过 5 分钟",
        symptom="节点上的 Pod 被驱逐或不可达，服务可用副本下降。",
        metric_queries=(
            'kube_node_status_condition{condition="Ready",status!="true"}',
            'node_load1{instance="$node"}',
        ),
        log_queries=(
            'NodeNotReady OR kubelet stopped posting node status',
            'network unavailable OR disk pressure OR memory pressure',
        ),
        root_causes=(
            "节点 kubelet 异常或节点宕机",
            "节点网络不可达",
            "磁盘压力或内存压力触发节点异常",
            "容器运行时异常",
        ),
        immediate_actions=(
            "确认节点是否可 SSH 和 kubelet 状态",
            "将核心负载迁移到健康节点",
            "对异常节点 cordon/drain",
            "必要时重启 kubelet 或替换节点",
        ),
        diagnosis_steps=(
            "查看 node describe 中 Conditions 和 Events",
            "检查 kubelet、containerd、网络插件日志",
            "查看节点 CPU、内存、磁盘和网络指标",
            "确认同机房或同可用区是否有批量异常",
        ),
        verification=(
            "节点 Ready 状态恢复",
            "Pod 重新调度完成",
            "服务可用副本数恢复",
        ),
        prevention=(
            "为节点系统组件增加健康巡检",
            "核心服务跨节点和跨可用区分布",
            "对节点压力类指标提前预警",
        ),
    ),
    ScenarioTemplate(
        code="redis_memory_high",
        alert_name="RedisMemoryHigh",
        category="缓存异常",
        severity="warning",
        service_roles=("cache", "app"),
        trigger="Redis 内存使用率连续 10 分钟超过 85%",
        symptom="Redis 淘汰 key 增加，命中率波动，严重时写入失败。",
        metric_queries=(
            'redis_memory_used_bytes / redis_memory_max_bytes',
            'rate(redis_evicted_keys_total[5m])',
        ),
        log_queries=(
            'OOM command not allowed OR evicted_keys',
            'redis memory high OR maxmemory',
        ),
        root_causes=(
            "缓存 key 数量异常增长",
            "TTL 缺失导致冷数据长期驻留",
            "大 value 写入 Redis",
            "maxmemory 配置小于业务峰值",
        ),
        immediate_actions=(
            "清理异常大 key 或过期冷 key",
            "临时提高 Redis 容量或扩容分片",
            "限制大 value 写入",
            "调整淘汰策略保护核心 key",
        ),
        diagnosis_steps=(
            "统计 key 前缀和大 key TopN",
            "查看 evicted_keys、used_memory、hit_rate",
            "确认最近是否有缓存结构变更",
            "检查 key TTL 分布",
        ),
        verification=(
            "内存使用率低于 70%",
            "evicted_keys 不再快速增长",
            "缓存命中率恢复",
        ),
        prevention=(
            "所有缓存 key 必须设置 TTL",
            "定期扫描大 key 和热 key",
            "新增缓存结构前进行容量评估",
        ),
    ),
    ScenarioTemplate(
        code="prometheus_scrape_failure",
        alert_name="PrometheusScrapeFailure",
        category="监控异常",
        severity="warning",
        service_roles=("monitor", "app", "collector"),
        trigger="Prometheus target scrape 失败率连续 10 分钟超过 20%",
        symptom="指标缺失，告警可能失真，监控看板出现断点。",
        metric_queries=(
            'up{job="$job"} == 0',
            'sum(rate(prometheus_target_scrapes_exceeded_sample_limit_total[5m])) by (job)',
        ),
        log_queries=(
            'scrape failed OR context deadline exceeded',
            'sample limit exceeded OR target down',
        ),
        root_causes=(
            "服务 metrics endpoint 不可达",
            "采集超时或样本量过大",
            "网络策略或安全组阻断",
            "Prometheus 负载过高",
        ),
        immediate_actions=(
            "确认 target endpoint 是否可访问",
            "临时提高 scrape timeout 或降低采集频率",
            "修复网络策略或服务发现配置",
            "减少高基数指标暴露",
        ),
        diagnosis_steps=(
            "查看 Prometheus targets 页面失败原因",
            "检查 target 服务健康状态",
            "查询 Prometheus 自身 CPU、内存和 TSDB 指标",
            "定位是否有高基数指标突增",
        ),
        verification=(
            "target up 恢复为 1",
            "scrape duration 低于 timeout",
            "看板指标断点恢复",
        ),
        prevention=(
            "限制高基数 label",
            "为核心 target 设置 scrape 失败告警",
            "Prometheus 按业务域拆分采集压力",
        ),
    ),
    ScenarioTemplate(
        code="log_collector_backlog",
        alert_name="LogCollectorBacklogHigh",
        category="日志采集异常",
        severity="warning",
        service_roles=("collector", "app", "worker"),
        trigger="日志采集队列积压连续 10 分钟增长",
        symptom="日志查询延迟，告警诊断缺少最新日志证据。",
        metric_queries=(
            'collector_queue_size{job="$job"}',
            'rate(collector_dropped_logs_total{job="$job"}[5m])',
        ),
        log_queries=(
            'collector backlog OR send failed OR retry',
            'rate limit exceeded OR log dropped',
        ),
        root_causes=(
            "日志量突增超过采集吞吐",
            "日志服务写入限流",
            "网络抖动导致发送失败重试",
            "采集 Agent 资源不足",
        ),
        immediate_actions=(
            "扩容采集 Agent 或提高发送并发",
            "临时降低 DEBUG 日志量",
            "检查日志服务限流和配额",
            "优先保留 ERROR/WARN 关键日志",
        ),
        diagnosis_steps=(
            "查看采集队列长度、丢弃量和发送失败率",
            "按服务统计日志量 TopN",
            "检查日志服务写入响应码",
            "确认最近是否开启了详细日志",
        ),
        verification=(
            "采集队列持续下降",
            "日志写入失败率归零",
            "查询延迟恢复正常",
        ),
        prevention=(
            "控制生产环境 DEBUG 日志",
            "为高日志量服务设置采样策略",
            "日志配额随业务峰值做容量规划",
        ),
    ),
    ScenarioTemplate(
        code="embedding_api_failure",
        alert_name="EmbeddingAPIFailureRateHigh",
        category="AI 服务异常",
        severity="critical",
        service_roles=("app", "worker"),
        trigger="Embedding API 调用失败率连续 5 分钟超过 5%",
        symptom="文档入库失败、RAG 检索缺失新知识、用户问题无法获得相关上下文。",
        metric_queries=(
            'sum(rate(embedding_request_errors_total{service="$service"}[5m])) by (error_code)',
            'histogram_quantile(0.95, sum(rate(embedding_request_duration_seconds_bucket[5m])) by (le))',
        ),
        log_queries=(
            'embedding failed OR DashScope OR rate limit',
            '429 OR timeout OR invalid api key',
        ),
        root_causes=(
            "Embedding 服务限流或配额耗尽",
            "API Key 无效或权限变更",
            "请求批量过大导致超时",
            "网络代理或 DNS 异常",
        ),
        immediate_actions=(
            "检查 API Key 和服务配额",
            "降低批量大小并启用重试退避",
            "暂停低优先级批量入库任务",
            "切换备用模型或备用账号",
        ),
        diagnosis_steps=(
            "按错误码统计 embedding 调用失败",
            "查看请求耗时、批量大小和输入长度",
            "检查 DashScope 服务状态和账号配额",
            "确认网络代理和 DNS 解析正常",
        ),
        verification=(
            "embedding 调用成功率恢复到 99% 以上",
            "文档入库任务恢复推进",
            "无新的限流或鉴权错误",
        ),
        prevention=(
            "增加配额水位告警",
            "入库任务做限速和断点续传",
            "对 embedding 失败记录建立重试队列",
        ),
    ),
    ScenarioTemplate(
        code="vector_index_failed",
        alert_name="VectorIndexBuildFailed",
        category="向量库异常",
        severity="critical",
        service_roles=("vector_db", "worker", "app"),
        trigger="向量索引构建任务失败或超过 30 分钟未完成",
        symptom="新增知识无法检索，RAG 回答缺少最新文档内容。",
        metric_queries=(
            'increase(vector_index_failures_total{service="$service"}[30m])',
            'vector_index_pending_tasks{service="$service"}',
        ),
        log_queries=(
            'index build failed OR MilvusException OR dimension mismatch',
            'collection not found OR insert failed OR embedding dimension',
        ),
        root_causes=(
            "向量维度和 collection schema 不匹配",
            "Milvus collection 不存在或未加载",
            "批量写入过大导致超时",
            "源文档格式异常或内容为空",
        ),
        immediate_actions=(
            "确认 embedding 维度和 Milvus schema 一致",
            "检查 collection 状态和连接配置",
            "降低批量写入大小后重试",
            "隔离格式异常的源文档",
        ),
        diagnosis_steps=(
            "查看向量索引任务日志中的首个异常",
            "查询 Milvus collection schema 和 load 状态",
            "检查 embedding 模型维度配置",
            "统计失败文档类型和文件大小",
        ),
        verification=(
            "失败任务重试成功",
            "新增文档可以被相似度检索命中",
            "Milvus insert 和 search 日志无异常",
        ),
        prevention=(
            "入库前做文档格式和维度校验",
            "索引任务增加失败重试和死信记录",
            "collection schema 变更需要迁移计划",
        ),
    ),
    ScenarioTemplate(
        code="certificate_expiring",
        alert_name="CertificateExpiringSoon",
        category="安全与证书",
        severity="warning",
        service_roles=("gateway", "app"),
        trigger="TLS 证书将在 14 天内过期",
        symptom="证书过期后 HTTPS 访问失败，客户端出现证书不可信错误。",
        metric_queries=(
            'probe_ssl_earliest_cert_expiry - time()',
            'ssl_certificate_expiry_seconds{domain="$domain"}',
        ),
        log_queries=(
            'certificate expired OR x509 OR TLS handshake failed',
            'cert-manager renewal failed OR secret not found',
        ),
        root_causes=(
            "证书自动续期失败",
            "DNS 校验或 HTTP 校验失败",
            "证书 Secret 未同步到 Ingress",
            "证书链配置不完整",
        ),
        immediate_actions=(
            "手动触发证书续期",
            "检查 cert-manager challenge 状态",
            "确认 DNS 解析和校验路径可访问",
            "更新 Ingress 引用的 Secret",
        ),
        diagnosis_steps=(
            "查看证书剩余有效期",
            "检查 Certificate、Order、Challenge 资源",
            "查看 cert-manager 日志",
            "验证域名证书链是否完整",
        ),
        verification=(
            "新证书有效期更新",
            "HTTPS 握手正常",
            "客户端无证书错误",
        ),
        prevention=(
            "证书过期提前 30/14/7 天多级告警",
            "续期失败告警直接通知值班",
            "证书 Secret 同步纳入发布检查",
        ),
    ),
    ScenarioTemplate(
        code="disk_io_high",
        alert_name="DiskIOHigh",
        category="存储异常",
        severity="warning",
        service_roles=("db", "vector_db", "queue", "app"),
        trigger="磁盘 IO 使用率连续 10 分钟超过 80%",
        symptom="读写延迟升高，数据库或日志写入变慢，应用响应抖动。",
        metric_queries=(
            'rate(node_disk_io_time_seconds_total[5m])',
            'rate(node_disk_read_time_seconds_total[5m]) + rate(node_disk_write_time_seconds_total[5m])',
        ),
        log_queries=(
            'i/o timeout OR disk io high OR fsync slow',
            'slow write OR WAL sync slow OR segment flush slow',
        ),
        root_causes=(
            "数据库 checkpoint、WAL 或 compaction 压力",
            "日志写入量突增",
            "批量导入或备份任务占用磁盘",
            "磁盘性能不足或云盘抖动",
        ),
        immediate_actions=(
            "暂停低优先级导入、备份或压缩任务",
            "将日志写入和数据盘隔离",
            "扩容磁盘 IOPS 或升级磁盘规格",
            "降低写入批量并增加缓冲",
        ),
        diagnosis_steps=(
            "查看磁盘 util、await、读写吞吐和 IOPS",
            "定位占用 IO 最高的进程和目录",
            "检查数据库 checkpoint/compaction 日志",
            "确认备份、导入、日志采集任务时间线",
        ),
        verification=(
            "磁盘 util 低于 60%",
            "读写 await 恢复到基线",
            "业务延迟抖动消失",
        ),
        prevention=(
            "IO 密集任务离峰执行",
            "关键数据库使用独立高性能磁盘",
            "建立磁盘延迟而不仅是容量告警",
        ),
    ),
]


def pick_services(template: ScenarioTemplate) -> list[ServiceProfile]:
    """为场景挑选适合的服务，保证数据覆盖不同业务域。"""
    matched = [service for service in SERVICES if service.role in template.service_roles]
    return matched


def render_markdown(template: ScenarioTemplate, service: ServiceProfile, index: int) -> str:
    """渲染单个运维知识文档。"""
    doc_id = f"AIOPS-{index:04d}-{template.code}-{service.name}"
    metric_lines = "\n".join(f"- `{query}`" for query in template.metric_queries)
    log_lines = "\n".join(f"- `{query}`" for query in template.log_queries)
    cause_lines = "\n".join(f"- {item}" for item in template.root_causes)
    immediate_lines = "\n".join(f"{idx}. {item}" for idx, item in enumerate(template.immediate_actions, 1))
    step_lines = "\n".join(f"{idx}. {item}" for idx, item in enumerate(template.diagnosis_steps, 1))
    verification_lines = "\n".join(f"- {item}" for item in template.verification)
    prevention_lines = "\n".join(f"- {item}" for item in template.prevention)

    return f"""# {service.name} - {template.alert_name} 运维处置知识

## 元数据

- 文档ID: `{doc_id}`
- 数据类型: `aiops_runbook`
- 告警名称: `{template.alert_name}`
- 告警分类: `{template.category}`
- 告警级别: `{template.severity}`
- 服务名称: `{service.name}`
- 服务角色: `{service.role}`
- 命名空间: `{service.namespace}`
- 责任团队: `{service.owner}`
- 日志主题: `{service.log_topic}`
- 指标 Job: `{service.metrics_job}`

## 触发条件

{template.trigger}

## 症状描述

{template.symptom}

## 推荐 PromQL

{metric_lines}

## 推荐日志查询

{log_lines}

## 常见根因

{cause_lines}

## 立即处置

{immediate_lines}

## 诊断步骤

{step_lines}

## 验证标准

{verification_lines}

## 预防措施

{prevention_lines}

## Agent 使用提示

当用户询问 `{service.name}` 的 `{template.alert_name}`、`{template.category}`、响应变慢、
资源异常、错误率升高或故障诊断时，应优先检索本文档，并结合 Prometheus 告警、
指标曲线和日志证据进行根因分析。
"""


def render_incident_markdown(template: ScenarioTemplate, service: ServiceProfile, index: int) -> str:
    """渲染单个故障案例文档。"""
    doc_id = f"AIOPS-INCIDENT-{index:04d}-{template.code}-{service.name}"
    primary_cause = template.root_causes[index % len(template.root_causes)]
    first_action = template.immediate_actions[index % len(template.immediate_actions)]
    second_action = template.immediate_actions[(index + 1) % len(template.immediate_actions)]
    verification = template.verification[index % len(template.verification)]
    log_query = template.log_queries[index % len(template.log_queries)]
    metric_query = template.metric_queries[index % len(template.metric_queries)]

    return f"""# {service.name} - {template.alert_name} 故障案例

## 元数据

- 文档ID: `{doc_id}`
- 数据类型: `aiops_incident_case`
- 告警名称: `{template.alert_name}`
- 告警分类: `{template.category}`
- 告警级别: `{template.severity}`
- 受影响服务: `{service.name}`
- 命名空间: `{service.namespace}`
- 责任团队: `{service.owner}`

## 事件摘要

`{service.name}` 触发 `{template.alert_name}`，触发条件为：{template.trigger}。
用户侧表现为：{template.symptom}

## 关键证据

### 指标证据

- 推荐查询: `{metric_query}`
- 异常现象: 告警窗口内指标持续高于阈值，且与服务错误率或延迟变化时间一致。

### 日志证据

- 推荐查询: `{log_query}`
- 日志主题: `{service.log_topic}`
- 证据模式: 日志中出现与 `{template.alert_name}` 相关的错误、超时、资源耗尽或重试记录。

## 根因判断

本案例的优先根因判断为：{primary_cause}

## 处置过程

1. {first_action}
2. {second_action}
3. 根据指标和日志证据确认影响范围，只处理异常实例或异常链路。
4. 处置后持续观察 30 分钟，避免故障反复。

## 恢复验证

- {verification}
- 告警状态恢复 normal 或不再 firing。
- 业务核心指标恢复到历史基线范围。

## 复盘关注点

- 告警是否足够早触发。
- 日志中是否能直接定位根因。
- 是否需要增加自动化恢复动作。
- 是否需要补充 runbook、监控指标或压测用例。
"""


def render_alert_rule_markdown(template: ScenarioTemplate, index: int) -> str:
    """渲染告警规则说明文档。"""
    doc_id = f"AIOPS-ALERT-RULE-{index:04d}-{template.code}"
    metric_lines = "\n".join(f"- `{query}`" for query in template.metric_queries)
    log_lines = "\n".join(f"- `{query}`" for query in template.log_queries)

    return f"""# {template.alert_name} 告警规则与诊断提示

## 元数据

- 文档ID: `{doc_id}`
- 数据类型: `aiops_alert_rule`
- 告警名称: `{template.alert_name}`
- 告警分类: `{template.category}`
- 默认级别: `{template.severity}`

## 告警语义

{template.trigger}

## 适用场景

{template.symptom}

## 推荐 PromQL 模板

{metric_lines}

## 推荐日志查询模板

{log_lines}

## 根因候选

{chr(10).join(f"- {item}" for item in template.root_causes)}

## 告警质量检查

- 告警表达式需要包含服务、实例、命名空间等定位标签。
- 告警 `for` 时间应覆盖短时抖动，避免误报。
- 告警注解中应包含排查入口、看板地址和 runbook 关键词。
- 同类告警需要避免多层重复通知，应区分 warning 和 critical。

## Agent 检索提示

用户询问 `{template.alert_name}`、`{template.category}`、告警规则、PromQL、
日志查询或故障诊断步骤时，应检索本文档。
"""


def build_record(
    template: ScenarioTemplate,
    service: ServiceProfile | None,
    index: int,
    content: str,
    doc_type: str,
) -> dict:
    """构造 JSONL 结构化记录。"""
    service_name = service.name if service else ""
    service_role = service.role if service else ""
    namespace = service.namespace if service else ""
    owner = service.owner if service else ""
    log_topic = service.log_topic if service else ""
    metrics_job = service.metrics_job if service else ""
    doc_id = (
        f"AIOPS-{index:04d}-{doc_type}-{template.code}-{service_name}"
        if service
        else f"AIOPS-{index:04d}-{doc_type}-{template.code}"
    )
    return {
        "id": doc_id,
        "doc_type": doc_type,
        "alert_name": template.alert_name,
        "category": template.category,
        "severity": template.severity,
        "service_name": service_name,
        "service_role": service_role,
        "namespace": namespace,
        "owner": owner,
        "log_topic": log_topic,
        "metrics_job": metrics_job,
        "trigger": template.trigger,
        "content": content,
        "metadata": {
            "source": "generated_aiops_seed_data",
            "doc_type": doc_type,
            "alert_name": template.alert_name,
            "category": template.category,
            "severity": template.severity,
            "service_name": service_name,
            "service_role": service_role,
            "namespace": namespace,
            "owner": owner,
        },
    }


def write_jsonl(records: list[dict]) -> None:
    """写出结构化 JSONL 数据。"""
    OUTPUT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    """生成全部 AIOps 种子数据。"""
    OUTPUT_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 清理旧的生成文档，避免模板调整后残留过期文件。
    for old_file in OUTPUT_DOCS_DIR.glob("*.md"):
        old_file.unlink()

    records: list[dict] = []
    index = 1

    for template in SCENARIOS:
        for service in pick_services(template):
            content = render_markdown(template, service, index)
            file_name = f"{index:04d}_runbook_{template.code}_{service.name}.md"
            (OUTPUT_DOCS_DIR / file_name).write_text(content, encoding="utf-8")
            records.append(build_record(template, service, index, content, "aiops_runbook"))
            index += 1

            incident_content = render_incident_markdown(template, service, index)
            incident_file_name = f"{index:04d}_incident_{template.code}_{service.name}.md"
            (OUTPUT_DOCS_DIR / incident_file_name).write_text(incident_content, encoding="utf-8")
            records.append(
                build_record(template, service, index, incident_content, "aiops_incident_case")
            )
            index += 1

    for template in SCENARIOS:
        alert_rule_content = render_alert_rule_markdown(template, index)
        alert_rule_file_name = f"{index:04d}_alert_rule_{template.code}.md"
        (OUTPUT_DOCS_DIR / alert_rule_file_name).write_text(alert_rule_content, encoding="utf-8")
        records.append(
            build_record(template, None, index, alert_rule_content, "aiops_alert_rule")
        )
        index += 1

    readme = f"""# Generated AIOps Seed Data

本目录由 `scripts/generate_aiops_seed_data.py` 自动生成。

- Markdown 文档数量: {len(records)}
- 用途: 作为 AIOps/RAG 知识库种子数据
- 推荐入库方式: 调用项目接口 `/api/index_directory`，目录参数传 `data/aiops_seed/generated_docs`

这些文档覆盖资源异常、性能异常、业务错误、数据库、缓存、消息队列、Kubernetes、
磁盘、Milvus 向量数据库等常见运维场景。
"""
    (OUTPUT_DOCS_DIR / "README.md").write_text(readme, encoding="utf-8")
    write_jsonl(records)

    print(f"生成 Markdown 文档: {len(records)} 个")
    print(f"文档目录: {OUTPUT_DOCS_DIR.resolve()}")
    print(f"结构化 JSONL: {OUTPUT_JSONL_PATH.resolve()}")


if __name__ == "__main__":
    main()
