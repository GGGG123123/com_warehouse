# 在 PowerShell 中运行
pip install pyyaml requests beautifulsoup4 markdownify tqdm lxml sentence-transformers faiss-cpu
python scripts/download_sources.py --catalog config/source_catalog_large.yaml --out output/raw --max_pages_per_site 1500
python scripts/build_ops_chunks.py --raw_dir output/raw --out output/ops_rag_chunks.jsonl --max_chars 3500
python scripts/build_faiss.py --input output/ops_rag_chunks.jsonl --out_dir output/faiss_index --model BAAI/bge-large-zh-v1.5
python scripts/search_demo.py --index_dir output/faiss_index --query "nginx 504 gateway timeout 怎么排查" --domain nginx
