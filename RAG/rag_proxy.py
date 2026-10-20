# -*- coding: utf-8 -*-
"""poemly 自动 RAG 代理 v5：检索注入 + 创作意图保护 + 韵书意图过滤
+ 流式哨兵截停 + max_tokens 钳制 + 【格式净化器：乱输出重排为标准三段式】。
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
MAX_TOKENS_CAP = 896

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

# ---------------- 格式净化器 ----------------
COUPLET = re.compile(r"^([\u4e00-\u9fff]{5,7})[，,]([\u4e00-\u9fff]{5,7})[。.]$")
SINGLE = re.compile(r"^([\u4e00-\u9fff]{5,7})[，,。.]?$")


def _clean_line(l):
    l = l.strip().strip(">").strip()
    l = re.sub(r"^[\"「'\-—*\d\.\s]+", "", l).strip()
    return l.rstrip("\"'」").strip()


def _parse_poem_lines(lines):
    """返回 (成对句列表, 起始索引)——最长连续诗句段；诗句间的解释行（含——）视为透明。"""
    best, best_start = [], -1
    cur, cur_start = [], -1
    for i, l in enumerate(lines):
        l2 = _clean_line(l)
        if "——" in l2 and len(l2) > 8:  # 解释行：跳过但不断诗句链
            continue
        m = COUPLET.match(l2)
        ok = bool(m) or (SINGLE.match(l2) and len(l2) in (5, 7))
        if ok:
            if cur_start == -1:
                cur_start = i
            if m:
                cur.append((m.group(1), m.group(2)))
            else:
                cur.append((l2, None))
        elif l2 and not ok:
            if len(cur) >= 2 and len(cur) > len(best):
                best, best_start = cur[:], cur_start
            cur, cur_start = [], -1
    if len(cur) >= 2 and len(cur) > len(best):
        best, best_start = cur[:], cur_start
    units = []
    for a, b in best:
        units.append(a)
        if b:
            units.append(b)
    if len(units) % 2 == 1:
        units = units[:-1]
    return units, best_start


def purify(text):
    """把混乱输出重排为标准三段式；识别不了则原样返回。"""
    if "诗" not in text and "《" not in text:
        return text
    lines = text.splitlines()
    units, pstart = _parse_poem_lines(lines)
    if len(units) < 4 or len(units) % 2 != 0:
        return text
    per = len(units[0])
    if per not in (5, 7) or any(len(u) != per for u in units):
        return text
    # 标题
    tm = re.search(r"《([^《》\n]{1,12})》", text)
    title = tm.group(1) if tm else "无题"
    # 立意
    lm = re.search(r"立意[：:]\s*([^\n]{4,60})", text)
    liyi = lm.group(1).strip().rstrip("。") + "。" if lm else f"以《{title}》为题，即景生情，托物见志。"
    # 意象解释：收集含"——"的行（按引句去重）
    seen, explains = set(), []
    for l in lines:
        l = _clean_line(l)
        if "——" in l and len(l) > 8:
            key = re.sub(r"[^\u4e00-\u9fff]", "", l)[:8]
            if key not in seen:
                seen.add(key)
                # 统一解释行格式："句"——解释
                l = re.sub(r"^([^\"']{1,14}?)——", r'"\1"——', l) if not l.startswith('"') else l
                explains.append(l)
    body = "\n".join(units[i] + "，" + units[i + 1] + "。" for i in range(0, len(units), 2))
    out = f"立意：{liyi}\n\n诗：\n《{title}》\n{body}\n\n意象解释：\n" + "\n".join(explains[:8])
    return out


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

    def _should_cut(self, acc):
        if len(acc) > 1300:
            return "硬顶"
        tail80 = acc[-80:]
        if len(acc) > 300 and len(tail80[-30:]) >= 12 and acc.count(tail80[-30:]) >= 2:
            return "复读"
        # 状态机：先有真诗节头（诗：\n《题》），其后的"意象解释："才算章节标记
        m_shi = re.search(r"诗[：:]\s*\n\s*《", acc)
        if not m_shi:
            return None
        after = acc[m_shi.end():]
        m_yi = re.search(r"意象解释[：:]", after)
        if not m_yi:
            return None
        tail = after[m_yi.end():]
        if re.search(r"\n\s*立意[：:]", tail) or re.search(r"诗[：:]\s*\n\s*《", tail):
            return "开新篇"
        if tail.count("《") >= 1 and len(re.sub(r"[^\u4e00-\u9fff]", "", tail)) > 260:
            return "疑似新诗"
        return None

    def _emit_text_sse(self, text, model="poemly", in_tok=1):
        out_tok = max(1, len(text) // 2)
        evs = []
        evs.append("event: message_start\ndata: " + json.dumps({
            "type": "message_start",
            "message": {"id": "msg_proxy_" + str(os.getpid()), "type": "message",
                        "role": "assistant", "model": model, "content": [],
                        "stop_reason": None, "stop_sequence": None,
                        "usage": {"input_tokens": in_tok, "output_tokens": 1}}}, ensure_ascii=False) + "\n")
        evs.append("event: content_block_start\ndata: " + json.dumps({
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""}}, ensure_ascii=False) + "\n")
        for j in range(0, len(text), 240):
            evs.append("event: content_block_delta\ndata: " + json.dumps({
                "type": "content_block_delta", "index": 0,
                "delta": {"type": "text_delta", "text": text[j:j + 240]}}, ensure_ascii=False) + "\n")
        evs.append("event: content_block_stop\ndata: " + json.dumps({
            "type": "content_block_stop", "index": 0}, ensure_ascii=False) + "\n")
        evs.append("event: message_delta\ndata: " + json.dumps({
            "type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok}}, ensure_ascii=False) + "\n")
        evs.append("event: message_stop\ndata: " + json.dumps({
            "type": "message_stop"}, ensure_ascii=False) + "\n")
        payload = ("\n".join(evs) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _relay_stream(self, resp):
        """缓冲全部文本（哨兵限流）→ 净化 → 一次性干净下发。"""
        acc = ""
        try:
            for raw in resp:
                line = raw.decode("utf-8", "replace")
                if line.startswith("data:"):
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                        acc += ev["delta"].get("text", "")
                        why = self._should_cut(acc)
                        if why:
                            print(f"[stop] 哨兵截停（{why}），已输出{len(acc)}字", flush=True)
                            break
        except Exception:
            pass
        finally:
            try:
                resp.close()
            except Exception:
                pass
        purified = purify(acc)
        if purified != acc:
            print(f"[fmt] 净化重排：{len(acc)}字 → {len(purified)}字", flush=True)
        self._emit_text_sse(purified)

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
                return
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
        data = resp.read()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"poemly RAG proxy v5 (净化器) on 127.0.0.1:{PORT} -> {UPSTREAM}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Proxy).serve_forever()
