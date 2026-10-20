# -*- coding: utf-8 -*-
"""v1.2 反抄袭数据集：作诗只用原创；真诗仅用于默写/赏析/出处/体裁辨识。"""
import json, os, re, random
from collections import Counter
from opencc import OpenCC
from imagery import IMAGERY, LINE_PATTERNS, ROLE_JUE, ROLE_LV, ADJ, LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, INSTR_TPL

random.seed(2027)
cc = OpenCC("t2s")
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"
GENRE_FULL = {"五绝": "五言绝句", "七绝": "七言绝句", "五律": "五言律诗", "七律": "七言律诗"}

# 平水韵
char2rhyme = {}
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    m = re.match(r"平水韵·(上平|下平)声([一二三四五六七八九十]+)(.)（韵部收字", line)
    if not m:
        continue
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    chars = re.split(r"【詞】", re.sub(r"（[^（）]*）", "", line.split("：", 1)[1]))[0]
    for c in chars:
        if "\u4e00" <= c <= "\u9fff":
            char2rhyme.setdefault(cc.convert(c), set()).add(name)

freq = Counter()
for fn in ["唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt"]:
    freq.update(c for c in open(os.path.join(KB, fn), encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")

NOIMG = ["\"{line}\"——{role}，写景如画，情在言外。", "\"{line}\"——句意{adj}，不假雕饰而韵味自出。", "\"{line}\"——此句{role}，平平道来，自有深致。"]

def find_img(line):
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        if w in line:
            return w, random.choice(imps if isinstance(imps, list) else [imps])
    return None, None

def explain(units):
    if len(units) == 4:
        seq = units
        roles = ROLE_JUE
    else:
        seq = [units[i * 2] + "，" + units[i * 2 + 1] + "。" for i in range(4)]
        roles = ROLE_LV
    out = []
    for u, r in zip(seq, roles):
        img, imp = find_img(u)
        if img is None:
            out.append(random.choice(NOIMG).format(line=u, role=r, adj=random.choice(ADJ)))
        else:
            out.append(random.choice(LINE_PATTERNS).format(line=u, img=img, imp=imp, imp2=imp, role=r, adj=random.choice(ADJ)))
    return "\n".join(out)

def liyi(title):
    key = next((k for k in EMO_BY_KEY if k in title), None)
    kw = {"送": "送别", "别": "离别", "思": "思念", "怀": "怀远", "咏": "咏物", "边": "边塞", "塞": "边塞",
          "归": "归乡", "书": "读书", "夜": "夜坐", "村": "村居", "田": "田家", "春": "春景", "秋": "秋景",
          "冬": "冬日", "夏": "夏日"}.get(key, title[:2])
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=EMO_BY_KEY.get(key, EMO_DEFAULT))

def poem_output(title, units):
    body = "\n".join(units[i] + "，" + units[i + 1] + "。" for i in range(0, len(units), 2))
    return f"立意：{liyi(title)}\n\n诗：\n《{title}》\n{body}\n\n意象解释：\n{explain(units)}"

samples = []

# ---------- 1) 作诗：仅原创（34金标准 + 44新原创），各2个指令变体 ----------
gold = json.load(open(os.path.join(TD, "poems_pilot.json"), encoding="utf-8"))
for d in gold:
    samples.append(dict(d))
orig = json.load(open(os.path.join(TD, "originals_v12.json"), encoding="utf-8"))
n_bad = 0
for p in orig:
    units = p["u"]
    n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
    if len(set(len(u) for u in units)) != 1 or n not in (5, 7) or len(units) not in (4, 8):
        n_bad += 1
        print("字数异常:", p["t"])
        continue
    feet = [u[-1] for u in units[1::2]]
    parts = [char2rhyme.get(f) for f in feet]
    if not all(parts) or not set.intersection(*parts):
        n_bad += 1
        print("韵脚异常:", p["t"], feet)
        continue
    for _ in range(2):
        samples.append({"instruction": random.choice(INSTR_TPL).format(t=p["t"], g=GENRE_FULL[p["g"]]),
                        "input": "", "output": poem_output(p["t"], units)})
print("作诗(原创):", len(samples), "（原创质检淘汰:", n_bad, "）")

# ---------- 2) 默写：真诗专用通道（明确要求背诵才给原文） ----------
def parse_file(fn):
    out = []
    for rec in open(os.path.join(KB, fn), encoding="utf-8").read().split("\n\n"):
        m = re.match(r"【[^】]+】《(.+?)》（(?:([^·）]*)·)?([^）]*)）\n(.+)", rec.strip(), re.S)
        if m:
            out.append(m.groups())
    return out

pool = parse_file("唐诗三百首.txt") + parse_file("千家诗.txt") + parse_file("宋词三百首.txt")
random.shuffle(pool)
recite = []
for title, _, author, body in pool:
    if len(recite) >= 300:
        break
    clean = body.replace("\n", "")
    if len(clean) < 12 or len(clean) > 200:
        continue
    qi = random.choice([f"请默写{author}的《{title}》", f"背诵一下《{title}》", f"帮我查《{title}》的原文（{author}）"])
    recite.append({"instruction": qi, "input": "",
                   "output": f"{author}《{title}》原文如下：\n{body}"})
samples += recite
print("+默写:", len(recite))

# ---------- 3) 赏析：给真诗讲意象（不触发创作映射） ----------
random.shuffle(pool)
anal = []
for title, _, author, body in pool:
    if len(anal) >= 300:
        break
    units = [u.strip() for u in re.split(r"[，。？！]", body) if u.strip()]
    if len(units) not in (4, 8) or len(set(len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units)) != 1:
        continue
    n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
    if n not in (5, 7):
        continue
    qi = random.choice([f"请解读{author}《{title}》的意象", f"赏析《{title}》各句", f"讲讲{author}这首《{title}》好在哪里"])
    anal.append({"instruction": qi, "input": "", "output": explain(units)})
samples += anal
print("+赏析:", len(anal))

# ---------- 4) 继承 v1 的问答资产（韵部/出处/体裁/身份）+ v1.1 检索增强 ----------
v1 = json.load(open(os.path.join(TD, "poemly_sft_v1.json"), encoding="utf-8"))
v11 = json.load(open(os.path.join(TD, "poemly_sft_v1_1.json"), encoding="utf-8"))
qa = [d for d in v1 if "诗：\n《" not in d["output"]]          # v1 全部非作诗样本
rag = [d for d in v11 if "_system" in d]                        # 检索增强样本
qa += rag
samples += qa
print("+问答/检索增强:", len(qa))

# 关键排除：v1 的作诗样本（真诗答案）一律不入 v1.2
random.shuffle(samples)
json.dump(samples, open(os.path.join(TD, "poemly_sft_v12.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("v1.2 总数:", len(samples))
