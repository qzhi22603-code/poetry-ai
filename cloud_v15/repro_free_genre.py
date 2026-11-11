# -*- coding: utf-8 -*-
"""v2.1 盲区复现：自由体裁指令实测 poemly-v2（经 11499 代理，完整诗阁路径）。"""
import json, time, urllib.request

PERSONA = "你是poemly，古典诗词创作助手。用韵依平水韵，讲究平仄对仗，绝不抄古人成句。写诗严格三段：立意：…／诗：…／意象解释：…，解释完立即停止；纯提问聊天则简洁作答，不要作诗。"

QUESTIONS = [
    "写一首咏物诗",
    "帮我写一首关于月亮的诗吧",
    "随便来一首诗",
]

for q in QUESTIONS:
    body = json.dumps({"model": "poemly-v2", "max_tokens": 400, "stream": True,
                       "system": PERSONA, "messages": [{"role": "user", "content": q}]}).encode()
    req = urllib.request.Request("http://127.0.0.1:11499/v1/messages", data=body,
                                 headers={"Content-Type": "application/json"})
    texts = []
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if line.startswith("data:"):
                p = line[5:].strip()
                if p and p != "[DONE]":
                    try:
                        ch = json.loads(p).get("choices", [{}])[0].get("delta", {})
                        t = ch.get("content") or ""
                        texts.append(t)
                    except Exception:
                        pass
    out = "".join(texts)
    print("Q:", q)
    print("A:", out[:400].replace("\n", " / "))
    print("=" * 60)
