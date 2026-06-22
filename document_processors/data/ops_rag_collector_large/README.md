# Ops RAG Collector Large

用于批量收集运维/SRE/RAG 文档的工具包。它支持：

- GitHub 仓库浅克隆
- 指定网页下载
- sitemap 抓取
- 本地 Markdown/HTML/YAML/CONF/LOG 清洗
- 按标题和长度切分为 RAG chunks
- 输出 JSONL

## 快速运行

```powershell
pip install pyyaml requests beautifulsoup4 markdownify tqdm lxml
python scripts/download_sources.py --catalog config/source_catalog_large.yaml --out output/raw --max_pages_per_site 800
python scripts/build_ops_chunks.py --raw_dir output/raw --out output/ops_rag_chunks.jsonl
```

如果要更多数据，把 `--max_pages_per_site` 调大，例如 3000。

## 输出

`output/ops_rag_chunks.jsonl` 每行一个 chunk：

```json
{
  "id": "...",
  "domain": "kubernetes",
  "component": "pod",
  "title": "Debug Pods",
  "content": "...",
  "source": "...",
  "embedding_text": "领域：kubernetes。组件：pod。标题：Debug Pods。内容：...",
  "metadata": {"domain": "kubernetes", "component": "pod"}
}
```

## 注意

- 第一次下载会很慢。
- GitHub 仓库很大时建议只拉浅克隆。
- 公开网页请遵守 robots.txt 和网站条款。
- 对于商业授权不清楚的内容，请只用于个人学习或替换为公司内部 runbook。
