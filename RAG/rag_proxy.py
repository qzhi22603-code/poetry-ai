# -*- coding: utf-8 -*-
"""poemly 自动 RAG 代理：架在 ZCode 与 Ollama 之间。
- 拦截 POST /v1/messages：取最后一条用户消息，bge-m3 检索知识库 top-3，
  作为附加 system 块注入，再转发给 Ollama（流式透传）。
- 其余请求原样转发（透明代理）。
- 任何检索失败都不阻塞对话（fail-open）。
监听 127.0.0.1:11499，上游 127.0.0.1:11434。
"""
import json, os, re, urllib.request, urllib.error
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAG = os.path.dirname(os.path.abspath(__file__))
UPSTREAM = "http://127.0.0.1:11434"
EMBED_URL = UPSTREAM + "/api/embed"
PORT = 11499
TOP_K = 3
CHAR_LIMIT = 320

CHUNKS = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
VECS = np.fromfile(os.path.join(RAG, "vectors.f32"), dtype=np.float32).reshape(-1, 1024)
VECS = VECS / np.maximum(np.linalg.norm(VECS, axis=1, keepdims=True), 1e-10)


def bigrams(s):
    s = re.sub(r"[^\u4e00-\u9fff]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s} if s else set()


def retrieve(query):
    req = urllib.request.Request(
        EMBED_URL,
        data=json.dumps({"model": "bge-m3", "input": [query]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        v = np.array(json.load(r)["embeddings"][0], dtype=np.float32)
    v = v / (np.linalg.norm(v) + 1e-10)
    score = 0.8 * (VECS @ v)
    bg = bigrams(query)
    if bg:
        kw = np.zeros(len(CHUNKS), dtype=np.float32)
        for i, c in enumerate(CHUNKS):
            kw[i] = len(bg & bigrams(c[:400])) / len(bg)
        score = score + 0.2 * kw
    order = np.argsort(score)[::-1]
    # 检索卫生：查询点名某韵书时，只注入该韵书条目，防交叉干扰
    intent = "平水韵" if "平水韵" in query else ("词林正韵" if "词林正韵" in query else None)
    top = []
    for i in order:
        c = CHUNKS[i][:20]
        if intent is None or (intent in c) or ("韵" not in c):
            top.append(i)
        if len(top) >= TOP_K:
            break
    parts = []
    for i in top:
        t = CHUNKS[i]
        # 韵表类密集字墙截短，防小模型复读退化
        if ("韵部收字" in t[:30] or "韵字：" in t[:30]) and len(t) > 170:
            t = t[:170] + "……（余字略）"
        parts.append(t[:CHAR_LIMIT])
    return "\n---\n".join(parts)


def last_user_text(messages):
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


INJECT_HEADER = (
    "【知识库检索结果】以下是针对用户本轮问题自动检索到的相关资料（韵表/诗词/典故原文），"
    "作答时依据这些资料；资料中没有的不要编造，可说明\"知识库未收录\"。这与你的创作准则一致。\n\n"
)


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _upstream(self, method, body=None, headers=None):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method)
        for k, v in (headers or {}).items():
            if k.lower() not in ("host", "content-length", "connection", "accept-encoding"):
                req.add_header(k, v)
        try:
            return urllib.request.urlopen(req, timeout=900)
        except urllib.error.HTTPError as e:
            return e

    def do_GET(self):
        self._relay("GET", None)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        if self.path.rstrip("/") == "/v1/messages":
            raw = self._inject(raw)
        self._relay("POST", raw)

    def _inject(self, raw):
        try:
            body = json.loads(raw)
            q = last_user_text(body.get("messages"))
            q = re.sub(r"\s+", " ", q).strip()[:200]
            if len(q) < 4 or "cache_control" in raw.decode("utf-8", "replace")[:0]:
                pass
            if len(q) >= 4:
                hits = retrieve(q)
                sysf = body.get("system")
                block = {"type": "text", "text": INJECT_HEADER + hits}
                if isinstance(sysf, list):
                    body["system"] = sysf + [block]
                elif isinstance(sysf, str) and sysf:
                    body["system"] = [{"type": "text", "text": sysf}, block]
                else:
                    body["system"] = [block]
                print(f"[rag] q={q[:40]} 注入{TOP_K}条", flush=True)
            return json.dumps(body, ensure_ascii=False).encode("utf-8")
        except Exception as e:
            print("[rag] 注入失败(fail-open):", e, flush=True)
            return raw

    def _relay(self, method, body):
        try:
            resp = self._upstream(method, body, dict(self.headers))
        except Exception as e:
            self.send_response(502)
            msg = json.dumps({"error": str(e)}).encode()
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        self.send_response(resp.code if hasattr(resp, "code") else 200)
        ctype = resp.headers.get("Content-Type", "application/json")
        self.send_header("Content-Type", ctype)
        if "event-stream" in ctype:
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                try: resp.close()
                except Exception: pass
            return
        data = resp.read()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"poemly RAG proxy on 127.0.0.1:{PORT} -> {UPSTREAM}, chunks={len(CHUNKS)}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
