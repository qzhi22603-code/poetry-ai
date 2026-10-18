# -*- coding: utf-8 -*-
"""poemly 知识库 MCP 检索服务器 v2（stdio）。
numpy 矢量检索 + 关键词混合评分；数据 chunks.json + vectors.f32，嵌入走本机 Ollama bge-m3。"""
import json, os, re, urllib.request
import numpy as np
from mcp.server.fastmcp import FastMCP

RAG = os.path.dirname(os.path.abspath(__file__))
EMBED_URL = "http://127.0.0.1:11434/api/embed"

mcp = FastMCP("poemly-kb")

CHUNKS = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
VECS = np.fromfile(os.path.join(RAG, "vectors.f32"), dtype=np.float32).reshape(-1, 1024)
_n = np.linalg.norm(VECS, axis=1, keepdims=True)
VECS = VECS / np.maximum(_n, 1e-10)


def embed(text):
    req = urllib.request.Request(
        EMBED_URL,
        data=json.dumps({"model": "bge-m3", "input": [text]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        v = np.array(json.load(r)["embeddings"][0], dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-10)


def bigrams(s):
    s = re.sub(r"[^\u4e00-\u9fff]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s} if s else set()


@mcp.tool()
def search_poetry_knowledge(query: str, top_k: int = 4) -> str:
    """检索本地古典诗词知识库，内容含：平水韵一百零六韵部字表、词林正韵十九部字表、全唐诗（约五万七千首）、唐诗三百首、宋词三百首、千家诗、声律启蒙、笠翁对韵、幼学琼林、龙文鞭影（典故）、人间词话、沧浪诗话。
    适用场景：①查某字属于平水韵/词林正韵哪个韵部、该韵部有哪些韵字 ②查证典故出处与含义 ③按篇名/诗句/作者找原诗 ④查对仗用语、历代词论诗论。
    query 填要查的内容（关键词或自然语言均可，含篇名作者更精准）；返回最相关的原文片段。作诗、论诗遇到需要查证的事实，请先调用本工具再作答。"""
    q = embed(query)
    cos = VECS @ q
    # 关键词混合：query 的二元组在片段中的覆盖率
    bg = bigrams(query)
    kw = np.zeros(len(CHUNKS), dtype=np.float32)
    if bg:
        for i, c in enumerate(CHUNKS):
            cb = bigrams(c[:600])
            kw[i] = len(bg & cb) / len(bg)
    score = 0.8 * cos + 0.2 * kw
    top = np.argsort(score)[-max(1, min(top_k, 8)):][::-1]
    return "\n\n---\n\n".join(f"[片段{i + 1}]\n{CHUNKS[i][:800]}" for i in top)


if __name__ == "__main__":
    mcp.run()
