import argparse, json, re, hashlib
from pathlib import Path
from tqdm import tqdm

HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.M)
FRONT_RE = re.compile(r'^---\n(.*?)\n---\n', re.S)

def parse_frontmatter(text):
    meta={}
    m=FRONT_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                meta[k.strip()] = v.strip()
        text=text[m.end():]
    return meta,text

def clean(text):
    text=re.sub(r'```[\s\S]*?```', lambda m: m.group(0)[:4000], text)
    text=re.sub(r'\n{3,}', '\n\n', text)
    text=re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def infer_component(title, content, path):
    s=(title+' '+content[:1000]+' '+str(path)).lower()
    pairs=[
        ('pod',['pod','crashloop','container','oomkilled']),('service',['service','endpoint','clusterip','nodeport']),('node',['node','kubelet','cordon','drain']),('ingress',['ingress','gateway','nginx']),('storage',['volume','pvc','pv','disk','watermark','filesystem']),('network',['dns','network','cni','calico','cilium','iptables']),('logs',['log','journalctl','logging','loki','promtail']),('backup_recovery',['backup','restore','recovery','dump','snapshot','wal','aof','rdb']),('replication',['replication','replica','primary','secondary','slave','master']),('alerting',['alert','alertmanager','rule','promql']),('security',['tls','ssl','cert','certificate','auth','secret','rbac']),('performance',['slow','latency','performance','cpu','memory','heap','throughput']),('configuration',['config','configuration','yaml','conf','settings'])]
    for comp,kws in pairs:
        if any(k in s for k in kws): return comp
    return 'general'

def split_by_headings(text, max_chars=3500, overlap=300):
    matches=list(HEADING_RE.finditer(text))
    if not matches:
        return [{'title':'', 'content': text[i:i+max_chars]} for i in range(0,len(text),max_chars-overlap)]
    blocks=[]
    for i,m in enumerate(matches):
        start=m.start(); end=matches[i+1].start() if i+1<len(matches) else len(text)
        title=m.group(2).strip(); content=text[start:end].strip()
        if len(content)<=max_chars:
            blocks.append({'title':title,'content':content})
        else:
            step=max_chars-overlap
            for j in range(0,len(content),step):
                part=content[j:j+max_chars]
                blocks.append({'title':title,'content':part})
    return blocks

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw_dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--max_chars', type=int, default=3500)
    args=ap.parse_args()
    raw=Path(args.raw_dir)
    files=list(raw.rglob('*'))
    out=Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    n=0
    with out.open('w',encoding='utf-8') as w:
        for p in tqdm(files):
            if not p.is_file(): continue
            try: txt=p.read_text(encoding='utf-8', errors='ignore')
            except: continue
            meta,body=parse_frontmatter(txt)
            body=clean(body)
            if len(body)<200: continue
            domain=meta.get('domain','unknown')
            source=meta.get('source_url') or meta.get('source_path') or str(p)
            blocks=split_by_headings(body,args.max_chars)
            for idx,b in enumerate(blocks):
                content=clean(b['content'])
                if len(content)<200: continue
                title=b['title'] or p.stem
                comp=infer_component(title,content,p)
                id_=hashlib.md5((str(p)+str(idx)+title).encode()).hexdigest()
                embedding_text=f"运维知识。领域：{domain}。组件：{comp}。标题：{title}。来源：{source}。内容：{content}"
                row={'id':id_,'domain':domain,'component':comp,'title':title,'content':content,'source':source,'embedding_text':embedding_text,'metadata':{'domain':domain,'component':comp,'source_name':meta.get('source_name',''),'source':source,'chunk_type':'ops_doc'}}
                w.write(json.dumps(row,ensure_ascii=False)+'\n')
                n+=1
    print(f'[OK] wrote {n} chunks -> {out}')
if __name__=='__main__': main()
