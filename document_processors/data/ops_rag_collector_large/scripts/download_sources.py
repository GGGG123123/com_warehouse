import argparse, os, subprocess, hashlib, re, time
from pathlib import Path
import yaml, requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
import xml.etree.ElementTree as ET

TEXT_EXTS = {'.md','.mdx','.rst','.txt','.yaml','.yml','.json','.conf','.cfg','.service','.xml','.adoc','.asciidoc','.1','.2','.3','.4','.5','.7','.8'}

def slug(s):
    return re.sub(r'[^a-zA-Z0-9_.-]+','_',s).strip('_')[:120]

def run(cmd, cwd=None):
    print('[CMD]', ' '.join(cmd))
    subprocess.run(cmd, cwd=cwd, check=False)

def clone_repo(src, out):
    name = src['name']
    target = out / 'repos' / name
    if target.exists():
        print(f'[SKIP] repo exists: {name}')
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    run(['git','clone','--depth','1',src['url'],str(target)])
    return target

def file_allowed(path, src):
    ext = path.suffix.lower()
    includes = set(src.get('include_ext') or [])
    if includes and ext not in includes:
        return False
    if ext not in TEXT_EXTS and not includes:
        return False
    rel = str(path).replace('\\','/')
    kws = src.get('include_keywords') or []
    if kws and not any(k.lower() in rel.lower() for k in kws):
        return False
    try:
        if path.stat().st_size > 2_000_000:
            return False
    except Exception:
        return False
    return True

def collect_repo_files(repo, out, src):
    dst = out / 'raw_docs' / src['name']
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in repo.rglob('*'):
        if not p.is_file():
            continue
        if '.git' in p.parts:
            continue
        if not file_allowed(p, src):
            continue
        rel = p.relative_to(repo)
        safe = slug(str(rel))
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        meta = f"---\nsource_name: {src['name']}\ndomain: {src.get('domain','unknown')}\nsource_url: {src['url']}\nsource_path: {rel}\n---\n\n"
        (dst / f'{safe}.md').write_text(meta + text, encoding='utf-8')
        count += 1
    print(f'[OK] {src["name"]}: collected {count} files')


def get_urls_from_sitemap(url, max_pages, include_keywords):
    try:
        r = requests.get(url, timeout=20, headers={'User-Agent':'ops-rag-collector/1.0'})
        r.raise_for_status()
    except Exception as e:
        print('[WARN] sitemap failed', url, e)
        return []
    urls=[]
    try:
        root = ET.fromstring(r.content)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        locs = [x.text for x in root.findall('.//sm:loc', ns)] or [x.text for x in root.findall('.//loc')]
        for loc in locs:
            if not loc:
                continue
            if loc.endswith('.xml') and len(urls) < max_pages:
                urls.extend(get_urls_from_sitemap(loc, max_pages-len(urls), include_keywords))
            else:
                if include_keywords and not any(k.lower() in loc.lower() for k in include_keywords):
                    continue
                urls.append(loc)
                if len(urls) >= max_pages:
                    break
    except Exception as e:
        print('[WARN] parse sitemap failed', e)
    return urls[:max_pages]

def fetch_page(url):
    r = requests.get(url, timeout=25, headers={'User-Agent':'ops-rag-collector/1.0'})
    r.raise_for_status()
    ctype = r.headers.get('content-type','')
    text = r.text
    if 'html' in ctype or '<html' in text[:500].lower():
        soup = BeautifulSoup(text, 'html.parser')
        for tag in soup(['script','style','nav','footer','header','aside']):
            tag.decompose()
        main = soup.find('main') or soup.find('article') or soup.body or soup
        return md(str(main), heading_style='ATX')
    return text

def collect_sitemap(src, out, max_pages):
    dst = out / 'raw_docs' / src['name']
    dst.mkdir(parents=True, exist_ok=True)
    urls = get_urls_from_sitemap(src['url'], max_pages, src.get('include_keywords') or [])
    count=0
    for u in tqdm(urls, desc=src['name']):
        try:
            text = fetch_page(u)
            if len(text.strip()) < 200:
                continue
            h = hashlib.md5(u.encode()).hexdigest()[:10]
            meta = f"---\nsource_name: {src['name']}\ndomain: {src.get('domain','unknown')}\nsource_url: {u}\n---\n\n"
            (dst / f'{h}_{slug(u)}.md').write_text(meta+text, encoding='utf-8')
            count += 1
            time.sleep(0.1)
        except Exception as e:
            print('[WARN] fetch failed', u, e)
    print(f'[OK] {src["name"]}: fetched {count} pages')

def collect_web_page(src, out):
    dst = out / 'raw_docs' / src['name']; dst.mkdir(parents=True, exist_ok=True)
    try:
        text = fetch_page(src['url'])
        meta = f"---\nsource_name: {src['name']}\ndomain: {src.get('domain','unknown')}\nsource_url: {src['url']}\n---\n\n"
        (dst / f'{slug(src["name"])}.md').write_text(meta+text, encoding='utf-8')
        print(f'[OK] page {src["name"]}')
    except Exception as e:
        print('[WARN] page failed', src['name'], e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--max_pages_per_site', type=int, default=800)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True, exist_ok=True)
    cfg=yaml.safe_load(Path(args.catalog).read_text(encoding='utf-8'))
    for src in cfg.get('sources',[]):
        typ=src.get('type')
        if typ=='github_repo':
            repo=clone_repo(src,out)
            collect_repo_files(repo,out,src)
        elif typ=='sitemap':
            collect_sitemap(src,out,args.max_pages_per_site)
        elif typ=='web_page':
            collect_web_page(src,out)
        else:
            print('[WARN] unknown type', typ)

if __name__=='__main__': main()
