import re, time, urllib.request

PROXY = "http://127.0.0.1:7897"
handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
opener = urllib.request.build_opener(handler)
opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36")]

html = open(r"C:\Users\38107\Desktop\ai\RAG\liweng-index.html", encoding="utf-8", errors="replace").read()
urls = sorted(set(re.findall(r'href="(/wiki/%E7%AC%A0%E7%BF%81%E5%B0%8D%E9%9F%BB/[^"&#]+)"', html)))
print("subpages:", len(urls))

out = []
for i, u in enumerate(urls, 1):
    url = "https://zh.wikisource.org" + u + "?action=raw"
    for attempt in range(3):
        try:
            with opener.open(url, timeout=30) as r:
                out.append(r.read().decode("utf-8"))
            break
        except Exception as e:
            print("retry", i, e)
            time.sleep(2)
    else:
        print("FAILED:", u)
    time.sleep(0.3)
print("fetched:", len(out))

import pickle
pickle.dump(out, open(r"C:\Users\38107\Desktop\ai\RAG\liweng-pages.pkl", "wb"))
print("sample page head:", out[0][:200] if out else "none")
