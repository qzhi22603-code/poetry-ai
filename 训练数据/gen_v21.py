# -*- coding: utf-8 -*-
# =====================================================================
# 【本文件在管线中的作用】
#   v2.1 盲区补丁生成器：治理"自由体裁指令跑偏"（盲测题3）。
#   问题：v2.0 只见过"请以《X》为题写一首五言绝句"这类带标准体裁词的指令，
#   一旦用户说"写一首咏物诗""随便来一首"，三段式就被截断。
#   药方：用 35 首金标准原诗做素材，套上"自由措辞"的指令外衣——
#   A 池（有题 175 条）：35 首 × 5 种自由句式 → 输出仍是标准三段式；
#   B 池（无题 30 条）：用户不指定题目，模型自选题自作 → 仍标准三段式。
#   产出 poemly_sft_v21.json = v1.5 全量 + 本补丁（去重洗牌）。
# 【执行前提】同目录 imagery.py；训练数据需 originals_v14.json、poemly_sft_v15.json。
#   运行：python gen_v21.py
# =====================================================================
"""v2.1：自由体裁指令补丁——措辞放开，格式收严。"""
import json, os, random
from imagery import LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, ROLE_JUE, ROLE_LV, ADJ, LINE_PATTERNS, IMAGERY

random.seed(45)
TD = r"C:\Users\38107\Desktop\ai\训练数据"

# ---- 与 gen_v15 同源的三个函数（素材已过质检，免韵表复核） ----
NOIMG = ["\"{line}\"——{role}，写景如画，情在言外。", "\"{line}\"——句意{adj}，不假雕饰而韵味自出。", "\"{line}\"——此句{role}，平平道来，自有深致。"]

def find_img(line):
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        if w in line:
            return w, random.choice(imps if isinstance(imps, list) else [imps])
    return None, None

def explain(units):
    seq = units if len(units) == 4 else [units[i*2] + "，" + units[i*2+1] + "。" for i in range(4)]
    roles = ROLE_JUE if len(units) == 4 else ROLE_LV
    out = []
    for u, r in zip(seq, roles):
        img, imp = find_img(u)
        out.append(random.choice(NOIMG).format(line=u, role=r, adj=random.choice(ADJ)) if img is None
                   else random.choice(LINE_PATTERNS).format(line=u, img=img, imp=imp, imp2=imp, role=r, adj=random.choice(ADJ)))
    return "\n".join(out)

def liyi(title):
    key = next((k for k in EMO_BY_KEY if k in title), None)
    kw = {"送": "送别", "思": "思念", "怀": "怀远", "咏": "咏物", "登": "登临",
          "侠": "侠气", "剑": "剑气", "酒": "酒意"}.get(key, title[:2])
    pool = EMO_BY_KEY.get(key, EMO_DEFAULT)
    emo = random.choice(pool) if isinstance(pool, list) else pool
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=emo)

def build_output(p):
    # 与 v1.5 完全一致的三段式答案（立意→诗→意象解释）
    units = p["u"]
    body = "\n".join(units[i] + "，" + units[i+1] + "。" for i in range(0, len(units), 2))
    return f"立意：{liyi(p['t'])}\n\n诗：\n《{p['t']}》\n{body}\n\n意象解释：\n{explain(units)}"

# ---- A 池：有题自由指令（35 首 × 5 句式） ----
poems = json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8"))
A_TPL = [
    "帮我写一首《{t}》吧",
    "以《{t}》为题赋诗一首",
    "我想读《{t}》，你替我写一首",
    "以《{t}》为题写首诗，体裁你定",
    "来一首《{t}》，越自然越好",
]
patch = []
for p in poems:
    out = build_output(p)
    for tpl in A_TPL:
        patch.append({"instruction": tpl.format(t=p["t"]), "input": "", "output": out})
print("A 池（有题自由指令）:", len(patch))

# ---- B 池：无题指令，模型自选题（指令 × 轮转原诗） ----
B_TPL = ["写一首咏物诗", "随便来一首诗", "帮我写首诗吧", "来一首即景的小诗", "写一首诗，题目你来定",
         "来一首", "给我作一首诗", "今晚想读首诗，你写来"]
rot = poems[:]
random.shuffle(rot)
for i, tpl in enumerate(B_TPL):
    for j in range(4):
        # 每种句式 4 条，共 32 条；原诗轮转（每首最多被无题指令用 1 次）
        p = rot[(i * 4 + j) % len(rot)]
        patch.append({"instruction": tpl, "input": "", "output": build_output(p)})
print("B 池（无题自选）:", len(patch) - len(poems) * len(A_TPL))

# ---- 合入 v1.5 全量并去重 ----
v15 = json.load(open(os.path.join(TD, "poemly_sft_v15.json"), encoding="utf-8"))
seen = set((d["instruction"], d["output"][:60]) for d in v15)
n_dup = 0
for d in patch:
    k = (d["instruction"], d["output"][:60])
    if k in seen:
        n_dup += 1
        continue
    seen.add(k)
    v15.append(d)
print("补丁去重剔除:", n_dup)

random.shuffle(v15)
json.dump(v15, open(os.path.join(TD, "poemly_sft_v21.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("v2.1 总数:", len(v15))
