# -*- coding: utf-8 -*-
"""增量追加知识条目到 chunks.json + vectors.f32（与 build_index.py 同规格：
bge-m3 嵌入、1024 维、L2 归一化、float32 追加）。用于免重建索引的小批量补录。"""
import json, os, sys, urllib.request
import numpy as np

KB = r"C:\Users\38107\Desktop\ai\知识库\韵部概览.txt"
RAG = os.path.dirname(os.path.abspath(__file__))
EMBED_URL = "http://127.0.0.1:11434/api/embed"

new_chunks = [r.strip() for r in open(KB, encoding="utf-8").read().split("\n\n") if r.strip()]
print("待追加条目:", len(new_chunks), flush=True)
for c in new_chunks:
    print("  -", c[:36] + "…", flush=True)

chunks = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
vec_path = os.path.join(RAG, "vectors.f32")
n_old_vecs = os.path.getsize(vec_path) // (1024 * 4)
print(f"现状: chunks={len(chunks)}  vectors={n_old_vecs}", flush=True)
assert len(chunks) == n_old_vecs, "chunks 与向量数不一致，先排查再追加！"

req = urllib.request.Request(
    EMBED_URL,
    data=json.dumps({"model": "bge-m3", "input": [c[:1000] for c in new_chunks]}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=900) as r:
    vs = json.load(r)["embeddings"]
arr = np.array(vs, dtype=np.float32)
assert arr.shape[1] == 1024, f"嵌入维度异常: {arr.shape}"
arr /= np.linalg.norm(arr, axis=1, keepdims=True)

# 先写向量（追加），再写 chunks（整体重写）——顺序保证任一时刻两者数量关系可判别
with open(vec_path, "ab") as f:
    f.write(arr.tobytes())
chunks.extend(new_chunks)
tmp = os.path.join(RAG, "chunks.json.tmp")
json.dump(chunks, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, os.path.join(RAG, "chunks.json"))

# 复核
chunks2 = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
n_new_vecs = os.path.getsize(vec_path) // (1024 * 4)
assert len(chunks2) == n_new_vecs, f"追加后不一致: {len(chunks2)} vs {n_new_vecs}"
tail = np.fromfile(vec_path, dtype=np.float32).reshape(-1, 1024)[-len(new_chunks):]
print("追加完成: chunks =", len(chunks2), " vectors =", n_new_vecs, flush=True)
print("末尾向量范数:", np.round(np.linalg.norm(tail, axis=1), 4).tolist(), flush=True)
