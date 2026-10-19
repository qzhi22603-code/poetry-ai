# -*- coding: utf-8 -*-
"""v1.1 补丁数据：检索增强样本（system 含【知识库检索结果】，答案依资料作答）。"""
import json, os, re, random
from opencc import OpenCC

random.seed(99)
cc = OpenCC("t2s")
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，讲究平仄对仗，先立意后作诗，写完逐联解意象，严禁编造典故。"

# 平水韵表（简体）
rhyme = {}
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    m = re.match(r"平水韵·(上平|下平)声([一二三四五六七八九十]+)(.)（韵部收字", line)
    if not m:
        continue
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    chars = re.split(r"【詞】", re.sub(r"（[^（）]*）", "", line.split("：", 1)[1]))[0]
    seen, simplified = set(), []
    for c in chars:
        if "\u4e00" <= c <= "\u9fff":
            s = cc.convert(c)
            if s not in seen:
                seen.add(s); simplified.append(s)
    rhyme[name] = simplified

# 语料频率排序常用字
from collections import Counter
freq = Counter()
for fn in ["唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt"]:
    freq.update(c for c in open(os.path.join(KB, fn), encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")

def table_block(name, w):
    same = [c for c in rhyme[name] if c != w and freq.get(c, 0) >= 5]
    same.sort(key=lambda c: -freq.get(c, 0))
    body = "".join(rhyme[name][:60])
    return (f"平水韵·{name}（韵部收字）：{body}……\n"
            f"提示：「{w}」在【{name}】部；常用同部字：{'、'.join(same[:16])}。")

INJECT_HEADER = "【知识库检索结果】以下为针对用户问题检索到的原文资料，作答须以此为准：\n\n"

samples = []

# 1) 韵部问答 ×180：一半纯检索增强，一半同题对照（无system资料的凭记忆版已在v1）
names = list(rhyme.keys())
qa_chars = []
for name in names:
    commons = [c for c in rhyme[name] if freq.get(c, 0) >= 100]
    if commons:
        qa_chars.append((random.choice(commons), name))
random.shuffle(qa_chars)
for w, name in qa_chars[:180]:
    block = table_block(name, w)
    qi = random.choice([
        f"「{w}」字在平水韵哪个韵部？同部有哪些常用字？",
        f"作近体诗用「{w}」作韵脚，该押哪一部？举些同部字。",
        f"「{w}」押平水韵哪一部？请列举同部常用字。",
    ])
    same = [c for c in rhyme[name] if c != w and freq.get(c, 0) >= 5]
    same.sort(key=lambda c: -freq.get(c, 0))
    ao = (f"「{w}」属平水韵【{name}】部。同部常用韵字有：{'、'.join(same[:16])}等。"
          "作近体诗时韵脚须与此部字相押（首句可借邻韵），不可出韵。")
    samples.append({"instruction": qi, "input": "", "output": ao,
                    "_system": PERSONA + "\n\n" + INJECT_HEADER + block})

# 2) 名句出处 ×150：system 注入原诗，答案引用原文
pool = []
for fn in ["唐诗三百首.txt", "宋词三百首.txt", "千家诗.txt"]:
    for rec in open(os.path.join(KB, fn), encoding="utf-8").read().split("\n\n"):
        m = re.match(r"【[^】]+】《(.+?)》（(?:([^·）]*)·)?([^）]*)）\n(.+)", rec.strip(), re.S)
        if m:
            pool.append(m.groups())
random.shuffle(pool)
for title, _, author, body in pool[:150]:
    first = body.split("。")[0].strip()
    if len(first) < 6 or len(first) > 40:
        continue
    samples.append({
        "instruction": f"「{first}」出自哪首诗？请引原文。",
        "input": "",
        "output": f"出自{author}的《{title}》：\n{body}",
        "_system": PERSONA + "\n\n" + INJECT_HEADER + f"【{fn[:-4]}】《{title}》（{author}）\n{body}"})

# 3) 混入 v1 的 500 条旧样本防遗忘
v1 = json.load(open(os.path.join(TD, "poemly_sft_v1.json"), encoding="utf-8"))
samples += random.sample(v1, 500)

random.shuffle(samples)
json.dump(samples, open(os.path.join(TD, "poemly_sft_v1_1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("v1.1 样本:", len(samples))
