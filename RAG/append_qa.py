# -*- coding: utf-8 -*-
"""把 qa_pilot.json 金标准问答增量写入 RAG（chunks.json + vectors.f32）。
规格与 append_overview.py 一致：bge-m3、1024 维、L2 归一化、float32 追加。
带去重保护：检测【诗阁金标准问答】标记防止重复追加。"""
import json, os, urllib.request
import numpy as np

QA = r"C:\Users\38107\Desktop\ai\训练数据\qa_pilot.json"
RAG = os.path.dirname(os.path.abspath(__file__))
EMBED_URL = "http://127.0.0.1:11434/api/embed"
MARK = "【诗阁金标准问答】"

qa = json.load(open(QA, encoding="utf-8"))
new_chunks = [MARK + "问：" + d["instruction"].strip() + "\n答：" + d["output"].strip() for d in qa]
print("待追加金标准条目:", len(new_chunks), flush=True)

chunks = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
if any(MARK in c for c in chunks):
    print("已存在金标准条目，跳过（防重复）。如需重灌请先手工清理。")
    raise SystemExit

vec_path = os.path.join(RAG, "vectors.f32")
n_old = os.path.getsize(vec_path) // (1024 * 4)
print(f"现状: chunks={len(chunks)}  vectors={n_old}", flush=True)
assert len(chunks) == n_old, "chunks 与向量数不一致，先排查再追加！"

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

with open(vec_path, "ab") as f:
    f.write(arr.tobytes())
chunks.extend(new_chunks)
tmp = os.path.join(RAG, "chunks.json.tmp")
json.dump(chunks, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, os.path.join(RAG, "chunks.json"))

chunks2 = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
n_new = os.path.getsize(vec_path) // (1024 * 4)
assert len(chunks2) == n_new, f"追加后不一致: {len(chunks2)} vs {n_new}"
tail = np.fromfile(vec_path, dtype=np.float32).reshape(-1, 1024)[-len(new_chunks):]
print("追加完成: chunks =", len(chunks2), " vectors =", n_new, flush=True)
print("末尾向量范数:", np.round(np.linalg.norm(tail, axis=1), 4).tolist(), flush=True)
