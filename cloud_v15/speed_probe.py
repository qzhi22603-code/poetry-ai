# -*- coding: utf-8 -*-
"""测量诗阁路径的耗时构成 + 观察 ollama 模型换载行为。"""
import json, time, urllib.request

PERSONA = "你是poemly，古典诗词创作助手。简洁作答。"

def proxy_q(q):
    body = json.dumps({"model": "poemly-v2", "max_tokens": 64, "stream": True,
                       "system": PERSONA, "messages": [{"role": "user", "content": q}]}).encode()
    req = urllib.request.Request("http://127.0.0.1:11499/v1/messages", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    first = None
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if line.startswith("data:") and first is None:
                first = time.time() - t0
    return first

def ps():
    with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as r:
        d = json.loads(r.read())
    return [(m.get("name"), m.get("size_vram", 0) // (1024*1024), m.get("size_cpu", 0) // (1024*1024)) for m in d.get("models", [])]

for i in range(3):
    f = proxy_q("以夏为题写一首七绝")
    print("第%d问 首字: %.1fs | 当前驻留:" % (i + 1, f), ps(), flush=True)
