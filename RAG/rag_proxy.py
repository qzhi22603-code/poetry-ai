# -*- coding: utf-8 -*-
"""poemly 自动 RAG 代理 v4：检索注入 + 创作意图保护 + 韵书意图过滤
+ 输出强制截停（流式哨兵：诗答结束后再开新篇→立刻掐流）+ 请求 max_tokens 钳制。
监听 127.0.0.1:11499，上游 127.0.0.1:11434。fail-open。"""
import json, os, re, urllib.request, urllib.error
import numpy as np
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAG = os.path.dirname(os.path.abspath(__file__))
UPSTREAM = "http://127.0.0.1:11434"
EMBED_URL = UPSTREAM + "/api/embed"
PORT = 11499
TOP_K = 3
CHAR_LIMIT = 320
MAX_TOKENS_CAP = 896          # 请求钳制
HARD_CHAR_CAP = 1500          # 流式硬顶（字符）

CHUNKS = json.load(open(os.path.join(RAG, "chunks.json"), encoding="utf-8"))
VECS = np.fromfile(os.path.join(RAG, "vectors.f32"), dtype=np.float32).reshape(-1, 1024)
VECS = VECS / np.maximum(np.linalg.norm(VECS, axis=1, keepdims=True), 1e-10)


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


def retrieve(query):
    v = embed(query)
    score = 0.8 * (VECS @ v)
    bg = bigrams(query)
    if bg:
        kw = np.zeros(len(CHUNKS), dtype=np.float32)
        for i, c in enumerate(CHUNKS):
            kw[i] = len(bg & bigrams(c[:400])) / len(bg)
        score = score + 0.2 * kw
    order = np.argsort(score)[::-1]
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
            raw = self._prepare(raw)
        self._relay("POST", raw)

    def _prepare(self, raw):
        """检索注入 + 创作意图保护 + max_tokens 钳制。"""
        try:
            body = json.loads(raw)
            if body.get("max_tokens"):
                body["max_tokens"] = min(int(body["max_tokens"]), MAX_TOKENS_CAP)
            q = last_user_text(body.get("messages"))
            q = re.sub(r"\s+", " ", q).strip()[:200]
            if (re.search(r"(写|作|赋|吟|填|来)(一?[首个]?)(.{0,6})(诗|词|绝句|律诗)", q)
                    and not re.search(r"查|出处|哪首|谁写|什么意思|介绍|评价|韵|典故|范|赏析", q)):
                print(f"[rag] 创作意图，跳过注入: {q[:40]}", flush=True)
                return json.dumps(body, ensure_ascii=False).encode("utf-8")
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

    # ---------- 流式哨兵 ----------
    def _should_cut(self, acc):
        if len(acc) > 1100:
            return "硬顶"
        # 近期重复检测（车轱辘话/复读）
        tail80 = acc[-80:]
        if len(acc) > 300 and acc.count(tail80[-30:]) >= 2 and len(tail80[-30:]) >= 12:
            return "复读"
        idx = acc.find("意象解释")
        if idx == -1:
            return None
        tail = acc[idx + 4:]
        if "立意" in tail or "诗：" in tail or "意象解释" in tail:
            return "开新篇"
        if tail.count("《") >= 1 and len(re.sub(r"[^\u4e00-\u9fff]", "", tail)) > 260:
            return "疑似新诗"
        if tail.count("——") > 10 or tail.count("\"") > 24:
            return "解释冗长"
        return None

    def _relay_stream(self, resp):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        acc = ""
        try:
            for raw in resp:
                line = raw.decode("utf-8", "replace")
                if line.startswith("data:"):
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        self.wfile.write(raw)
                        self.wfile.flush()
                        continue
                    if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                        acc += ev["delta"].get("text", "")
                        why = self._should_cut(acc)
                        if why:
                            print(f"[stop] 哨兵截停（{why}），已输出{len(acc)}字", flush=True)
                            term = ("event: content_block_stop\n"
                                    'data: {"type":"content_block_stop","index":0}\n\n'
                                    "event: message_delta\n"
                                    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
                                    '"usage":{"input_tokens":1,"output_tokens":1}}\n\n'
                                    "event: message_stop\n"
                                    'data: {"type":"message_stop"}\n\n')
                            self.wfile.write(term.encode("utf-8"))
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return
                self.wfile.write(raw)
                self.wfile.flush()
        except Exception:
            pass
        finally:
            try:
                resp.close()
            except Exception:
                pass

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
        ctype = resp.headers.get("Content-Type", "application/json")
        if "event-stream" in ctype:
            if self.path.rstrip("/") == "/v1/messages":
                self._relay_stream(resp)
            else:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
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
                    try:
                        resp.close()
                    except Exception:
                        pass
            return
        self.send_response(resp.code if hasattr(resp, "code") else 200)
        self.send_header("Content-Type", ctype)
        data = resp.read()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"poemly RAG proxy v4 on 127.0.0.1:{PORT} -> {UPSTREAM}, chunks={len(CHUNKS)}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
