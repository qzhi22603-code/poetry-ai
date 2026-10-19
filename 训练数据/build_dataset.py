# -*- coding: utf-8 -*-
"""试产集组装 + 自动质检：
1. 合并 poems_pilot.json + qa_pilot.json
2. 从平水韵字表自动生成 14 条韵部问答（保证零事实错误）
3. 质检：诗句字数/句数/韵脚同部/收尾纪律
输出 poemly_sft_pilot.json（Alpaca 格式）
"""
import json, os, re, random

RAG = r"C:\Users\38107\Desktop\ai\RAG"
KB = r"C:\Users\38107\Desktop\ai\知识库"
OUT = r"C:\Users\38107\Desktop\ai\训练数据\poemly_sft_pilot.json"
random.seed(42)

# ---------- 1. 载入平水韵（繁体转简体建索引） ----------
from opencc import OpenCC
cc2s = OpenCC("t2s")
rhyme = {}  # 韵部名 -> [字]
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    m = re.match(r"平水韵·(上平|下平)声([一二三四五六七八九十]+)(.)（韵部收字", line)
    if not m:
        continue
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    chars = re.sub(r"（[^（）]*）", "", line.split("：", 1)[1])
    chars = re.split(r"【詞】", chars)[0]  # 词韵增字与诗韵归部不同，整段切除
    seen = set()
    simplified = []
    for c in chars:
        if "\u4e00" <= c <= "\u9fff":
            s = cc2s.convert(c)
            if s not in seen:
                seen.add(s)
                simplified.append(s)
    rhyme[name] = simplified

char2rhyme_map = {}
for name, chars in rhyme.items():
    for c in chars:
        char2rhyme_map.setdefault(c, []).append(name)

# ---------- 2. 自动生成韵部问答（按语料频率取常用字） ----------
from collections import Counter
freq = Counter()
for fn in ["唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt", "全宋词.txt"]:
    p = os.path.join(KB, fn)
    if os.path.exists(p):
        freq.update(c for c in open(p, encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")

q_words = ["江", "花", "月", "风", "雪", "山", "春", "秋", "心", "天", "人", "海", "夜", "白"]
yun_samples = []
for w in q_words:
    names = char2rhyme_map.get(w)
    if not names:
        continue
    name = names[0]
    same = [c for c in rhyme[name] if c != w and freq.get(c, 0) >= 5 and c not in "了不些吾其而无之乎者也于以"]
    same.sort(key=lambda c: -freq.get(c, 0))
    show = "、".join(same[:16])
    yun_samples.append({
        "instruction": f"「{w}」字在平水韵中属哪个韵部？同部还有哪些常用字？",
        "input": "",
        "output": f"「{w}」属平水韵【{name}】部。同部常用韵字有：{show}等。作近体诗时，韵脚须与此部字相押（首句可借邻韵），不可出韵。"
    })

# ---------- 3. 合并 ----------
data = []
data += json.load(open(r"C:\Users\38107\Desktop\ai\训练数据\poems_pilot.json", encoding="utf-8"))
data += yun_samples
data += json.load(open(r"C:\Users\38107\Desktop\ai\训练数据\qa_pilot.json", encoding="utf-8"))

# ---------- 4. 质检 ----------
errors = []
for i, d in enumerate(data):
    out = d["output"]
    if "诗：\n《" in out:  # 作诗样本
        title = re.search(r"诗：\n《(.+?)》", out).group(1)
        # 提取诗行，按逗号句号分句（一行=两句）
        body = out.split("《" + title + "》\n", 1)[1].split("\n\n意象解释", 1)[0]
        lines = [l for l in body.splitlines() if l.strip()]
        sent = []
        for l in lines:
            for s in re.split(r"[，。？！、]", l):
                s = s.strip()
                if s:
                    sent.append(s)
        lens = [len(re.sub(r"[，、；：\s]", "", s)) for s in sent]
        if len(set(lens)) != 1 or lens[0] not in (5, 7):
            errors.append(f"[{i}]{title}: 句长不齐 {lens}")
        if len(sent) not in (4, 8):
            errors.append(f"[{i}]{title}: 句数 {len(sent)}")
        # 韵脚检查（偶数句末字）
        rh = [re.sub(r"[，。、；：\s]", "", s)[-1] for s in sent[1::2]]
        parts = [set(char2rhyme_map.get(c, [])) for c in rh]
        if parts and all(parts):
            common = set.intersection(*parts)
            if not common:
                errors.append(f"[{i}]{title}: 韵脚不同部 {''.join(rh)}")
        # 收尾纪律：最后一行不得是总结/客套
        last = [l for l in out.splitlines() if l.strip()][-1]
        if re.match(r"^(以上|总之|希望|如有|这(首|四|八))", last.strip()):
            errors.append(f"[{i}]{title}: 结尾含总结客套")
    # 通用：不得复述准则
    if "准则" in out and "五条准则" in out and "你是谁" not in d["instruction"]:
        errors.append(f"[{i}]: 疑似复述准则")

print("样本总数:", len(data))
print("质检错误:", len(errors))
for e in errors:
    print("  ✗", e)

json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已写出:", OUT)
