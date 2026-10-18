# -*- coding: utf-8 -*-
"""通用维基文库抓取器：给定作品名，抓主页面+全部子页，存 pkl。"""
import re, sys, time, pickle, urllib.request, urllib.parse

PROXY = "http://127.0.0.1:7897"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
opener.addheaders = [("User-Agent", UA)]

def fetch_raw(title):
    url = "https://zh.wikisource.org/zh-hans/" + urllib.parse.quote(title) + "?action=raw"
    for _ in range(3):
        try:
            with opener.open(url, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            print("  retry:", e); time.sleep(2)
    return None

def subpage_links(title):
    """从 HTML 提取子页链接（去重排序）。"""
    url = "https://zh.wikisource.org/zh-hans/" + urllib.parse.quote(title)
    try:
        with opener.open(url, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        print("  index fail:", e); return []
    pat = 'href="/zh-hans/' + urllib.parse.quote(title) + '/'
    links = set()
    for m in re.finditer(r'href="(' + re.escape("/zh-hans/" + urllib.parse.quote(title)) + r'/[^"&#]+)"', html):
        links.add(urllib.parse.unquote(m.group(1).split("/zh-hans/", 1)[1]))
    return sorted(links)

def grab(work):
    print("==", work)
    pages = [(work, fetch_raw(work))]
    subs = subpage_links(work)
    print("  subpages:", len(subs))
    for s in subs:
        raw = fetch_raw(s)
        if raw: pages.append((s, raw))
        time.sleep(0.3)
    pages = [(t, r) for t, r in pages if r]
    print("  fetched:", len(pages))
    return pages

if __name__ == "__main__":
    works = sys.argv[1:]
    for w in works:
        pages = grab(w)
        out = r"C:\Users\38107\Desktop\ai\RAG\ws-" + w.replace("/", "-") + ".pkl"
        pickle.dump(pages, open(out, "wb"))
        print("  saved:", out, "chars:", sum(len(r) for _, r in pages))
