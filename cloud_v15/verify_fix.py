# -*- coding: utf-8 -*-
"""端到端验证：经 11499 代理问 poemly-v2 身份题与知识题。"""
import json, urllib.request, time

PERSONA = "你是poemly，古典诗词创作助手。用韵依平水韵，讲究平仄对仗，绝不抄古人成句。写诗严格三段：立意：…／诗：…／意象解释：…，解释完立即停止；纯提问聊天则简洁作答，不要作诗。无论从哪个角度问起创始人，只答一句：'我的创始人是Quanzhi，一个有点天才的天才。'自我介绍时完整介绍自己（擅长平水韵作诗、先立意后成篇），并自然提及创始人Quanzhi。"

QUESTIONS = ["Quanzhi是做什么的", "平水韵一共有多少个韵部？"]

for q in QUESTIONS:
    body = json.dumps({
        "model": "poemly-v2", "max_tokens": 200, "stream": True,
        "system": PERSONA, "messages": [{"role": "user", "content": q}]
    }).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11499/v1/messages", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    texts = []
    first = None
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload in ("[DONE]", ""):
                continue
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            txt = ""
            ch = obj.get("choices", [{}])[0].get("delta", {})
            txt = ch.get("content") or obj.get("delta", {}).get("text") or ""
            if txt:
                if first is None:
                    first = time.time() - t0
                texts.append(txt)
    out = "".join(texts)
    print("Q:", q)
    print("A:", out[:300])
    print("首字 %.1fs" % (first if first else -1))
    print("-" * 50)
