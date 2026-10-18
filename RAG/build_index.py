# -*- coding: utf-8 -*-
"""重建索引（v2）：知识库/*.txt → chunks.json + vectors.f32（numpy 归一化矩阵）。"""
import json, os, time, urllib.request
import numpy as np

KB = r"C:\Users\38107\Desktop\ai\知识库"
RAG = os.path.dirname(os.path.abspath(__file__))
EMBED_URL = "http://127.0.0.1:11434/api/embed"

records = []
for fn in sorted(os.listdir(KB)):
    if fn.endswith(".txt"):
        text = open(os.path.join(KB, fn), encoding="utf-8").read()
        records.extend(r.strip() for r in text.split("\n\n") if r.strip())
print("total chunks:", len(records), flush=True)

vecs = np.zeros((len(records), 1024), dtype=np.float32)
B, MAX_CHARS = 64, 16000
t0 = time.time()
done = 0

def flush(start, batch):
    global done
    import time as _t, urllib.error
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                EMBED_URL,
                data=json.dumps({"model": "bge-m3", "input": batch}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=900) as r:
                vs = json.load(r)["embeddings"]
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            print(f"  HTTP {e.code} attempt {attempt+1}: {body}", flush=True)
            if attempt == 4:
                raise
            _t.sleep(3 * (attempt + 1))
    dim = len(vs[0])
    arr = np.array(vs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    vecs[start:start + len(batch), :dim] = arr
    done += len(batch)
    if (done // B) % 20 == 0:
        print(f"{done}/{len(records)}  {time.time() - t0:.0f}s", flush=True)

batch, chars, start = [], 0, 0
for i, rec in enumerate(records):
    r = rec[:1000]  # 嵌入输入截断，避免超长诗撑爆请求
    if len(batch) >= B or (batch and chars + len(r) > MAX_CHARS):
        flush(start, batch)
        batch, chars, start = [], 0, i
    batch.append(r)
    chars += len(r)
if batch:
    flush(start, batch)

json.dump(records, open(os.path.join(RAG, "chunks.json"), "w", encoding="utf-8"), ensure_ascii=False)
vecs.tofile(os.path.join(RAG, "vectors.f32"))
print("DONE", len(records), "chunks,", f"{time.time() - t0:.0f}s,", vecs.nbytes // 1024 // 1024, "MB vectors", flush=True)
