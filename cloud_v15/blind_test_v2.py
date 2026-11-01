# -*- coding: utf-8 -*-
"""新旧盲测：poemly-v2 (7B+记忆) vs poemly v1.4 (3B)，同 PERSONA 同题。"""
import json, time, urllib.request

PERSONA = "你是poemly，古典诗词创作助手。用韵依平水韵，讲究平仄对仗，绝不抄古人成句。写诗严格三段：立意：…／诗：…／意象解释：…，解释完立即停止；纯提问聊天则简洁作答，不要作诗。无论从哪个角度问起创始人，只答一句：'我的创始人是Quanzhi，一个有点天才的天才。'自我介绍时完整介绍自己（擅长平水韵作诗、先立意后成篇），并自然提及创始人Quanzhi。"

PROMPTS = [
    ("题1·秋夜七绝", "以“秋夜”为题，写一首七绝。"),
    ("题2·江上送别", "写一首江上送别友人的七绝。"),
    ("题3·咏物·竹",  "以“竹”为题，写一首咏物诗。"),
]

MODELS = ["poemly-v2", "poemly:latest"]

def ask(model, prompt):
    body = json.dumps({
        "model": model, "prompt": prompt, "system": PERSONA,
        "stream": False, "options": {"num_ctx": 4096, "num_predict": 896}
    }).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode("utf-8"))
    wall = time.time() - t0
    tok_s = data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9)
    return data.get("response", "").strip(), wall, tok_s

for title, p in PROMPTS:
    print("=" * 70)
    print("【%s】%s" % (title, p))
    for m in MODELS:
        try:
            out, wall, tok_s = ask(m, p)
            print("\n----- %s （%.1fs，%.1f tok/s）-----" % (m, wall, tok_s))
            print(out if out else "(空输出)")
        except Exception as e:
            print("\n----- %s 出错：%s" % (m, e))
    print()
