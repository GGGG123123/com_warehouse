import argparse,json
from pathlib import Path
import numpy as np, faiss
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--out_dir',required=True); ap.add_argument('--model',default='BAAI/bge-large-zh-v1.5'); ap.add_argument('--batch_size',type=int,default=16)
    args=ap.parse_args(); out=Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    docs=[json.loads(l) for l in Path(args.input).read_text(encoding='utf-8').splitlines() if l.strip()]
    model=SentenceTransformer(args.model)
    texts=[d['embedding_text'] for d in docs]
    embs=[]
    for i in tqdm(range(0,len(texts),args.batch_size)):
        embs.append(model.encode(texts[i:i+args.batch_size], normalize_embeddings=True))
    emb=np.asarray(np.vstack(embs),dtype='float32')
    index=faiss.IndexFlatIP(emb.shape[1]); index.add(emb)
    faiss.write_index(index, str(out/'index.faiss'))
    with (out/'docs.jsonl').open('w',encoding='utf-8') as f:
        for d in docs: f.write(json.dumps(d,ensure_ascii=False)+'\n')
    (out/'embedding_model.txt').write_text(args.model,encoding='utf-8')
    print('[OK] faiss index built', len(docs))
if __name__=='__main__': main()
