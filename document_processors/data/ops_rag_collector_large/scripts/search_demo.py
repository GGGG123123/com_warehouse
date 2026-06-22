import argparse,json
from pathlib import Path
import numpy as np, faiss
from sentence_transformers import SentenceTransformer

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--index_dir',required=True); ap.add_argument('--query',required=True); ap.add_argument('--domain',default=''); ap.add_argument('--top_k',type=int,default=8)
    args=ap.parse_args(); idxdir=Path(args.index_dir)
    model_name=(idxdir/'embedding_model.txt').read_text(encoding='utf-8').strip()
    model=SentenceTransformer(model_name)
    docs=[json.loads(l) for l in (idxdir/'docs.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    index=faiss.read_index(str(idxdir/'index.faiss'))
    q=model.encode([args.query], normalize_embeddings=True).astype('float32')
    D,I=index.search(q, min(args.top_k*10, len(docs)))
    shown=0
    for score,i in zip(D[0],I[0]):
        d=docs[i]
        if args.domain and d.get('domain')!=args.domain: continue
        print('\n---', shown+1, 'score=', float(score))
        print('domain:', d.get('domain'), 'component:', d.get('component'))
        print('title:', d.get('title'))
        print('source:', d.get('source'))
        print(d.get('content','')[:500].replace('\n',' '))
        shown+=1
        if shown>=args.top_k: break
if __name__=='__main__': main()
