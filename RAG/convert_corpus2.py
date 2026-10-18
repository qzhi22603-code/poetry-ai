# -*- coding: utf-8 -*-
"""第二批语料转换：词林正韵/人间词话/沧浪诗话/龙文鞭影/全唐诗 → 知识库 txt。"""
import json, os, re, pickle
from opencc import OpenCC

RAG = r"C:\Users\38107\Desktop\ai\RAG"
KB = r"C:\Users\38107\Desktop\ai\知识库"
cc = OpenCC("t2s")

def save(name, records):
    recs = [r.strip() for r in records if r.strip()]
    path = os.path.join(KB, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(recs) + "\n")
    print(f"{name}: {len(recs)} 条, {os.path.getsize(path)//1024} KB")

def clean_wiki(text, drop_headers=True):
    """通用 wikitext 清洗：模板/注释/链接/加粗等。"""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)  # 二层
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<poem>|</poem>|<ref[^>]*>.*?</ref>|__\w+__", "", text, flags=re.S)
    text = text.replace("'''", "").replace("''", "")
    return text

# 1. 词林正韵（繁体保留，同平水韵）
raw = pickle.load(open(os.path.join(RAG, "ws-词林正韵.pkl"), "rb"))[0][1]
records, bu, sheng = [], "", ""
for line in raw.splitlines():
    line = line.strip()
    m = re.match(r"^==+\s*第([一二三四五六七八九十]+)部\s*==+$", line)
    if m:
        bu = "第" + m.group(1) + "部"; continue
    m = re.match(r"^===+\s*(平聲|仄聲|入聲)[：:]?(.*?)=+\s*$", line)
    if m:
        sheng = m.group(1) + ("" if not m.group(2) else "（" + m.group(2).strip("= ：:") + "）"); continue
    m = re.match(r"^【(.+?)】(.+)$", line)
    if m and bu:
        records.append(f"词林正韵·{bu}{sheng}·【{m.group(1)}】韵字：{m.group(2).strip()}")
save("词林正韵字表.txt", records)

# 2. 人间词话（每则一条，转简体）
raw = pickle.load(open(os.path.join(RAG, "ws-人间词话.pkl"), "rb"))[0][1]
body = clean_wiki(raw)
records = []
for para in body.splitlines():
    para = para.strip().strip("\u3000").strip()
    if not para or para.startswith("|") or para.startswith("="):
        continue
    if re.search(r"[\u4e00-\u9fff]", para) and len(para) >= 8:
        records.append("【人间词话】" + cc.convert(para))
save("人间词话.txt", records)

# 3. 沧浪诗话（每则一条，带卷名）
pages = pickle.load(open(os.path.join(RAG, "ws-沧浪诗话.pkl"), "rb"))
juan_names = {"卷1": "诗辨", "卷2": "诗体", "卷3": "诗法", "卷4": "诗评", "卷5": "考证", "附录": "附录"}
records = []
for title, raw in pages:
    juan = title.split("/")[-1]
    name = juan_names.get(juan, juan)
    body = clean_wiki(raw)
    for para in body.splitlines():
        para = para.strip().strip("\u3000").strip()
        if para.startswith("=") or not para:
            continue
        if re.search(r"[\u4e00-\u9fff]", para) and len(para) >= 8:
            records.append(f"【沧浪诗话·{cc.convert(name)}】" + cc.convert(para))
save("沧浪诗话.txt", records)

# 4. 龙文鞭影（按韵部小节逐行，转简体）
raw = pickle.load(open(os.path.join(RAG, "ws-龙文鞭影.pkl"), "rb"))[0][1]
records, sect = [], ""
for line in raw.splitlines():
    line = line.strip()
    if not line or line.startswith("{{") or line.startswith("|"):
        continue
    m = re.match(r"^=+\s*([^=]+?)\s*=+$", line)
    if m and not line.startswith("==="):
        sect = cc.convert(m.group(1)); continue
    line = re.sub(r"</?poem>", "", line).strip()
    if sect and re.search(r"[\u4e00-\u9fff]", line) and "：" not in line[:2]:
        records.append(f"【龙文鞭影·{sect}】" + cc.convert(line))
save("龙文鞭影.txt", records)

# 5. 全唐诗（每首一条，转简体，按 id 去重）
records, seen, total = [], set(), 0
for fn in sorted(os.listdir(os.path.join(RAG, "tang"))):
    if not fn.endswith(".json"):
        continue
    try:
        poems = json.load(open(os.path.join(RAG, "tang", fn), encoding="utf-8"))
    except Exception as e:
        print("skip", fn, e); continue
    for p in poems:
        total += 1
        pid = p.get("id")
        if pid in seen:
            continue
        seen.add(pid)
        title = cc.convert(p.get("title", "无题"))
        author = cc.convert(p.get("author", "佚名"))
        body = "".join(cc.convert(x) for x in p.get("paragraphs", []))
        if body:
            records.append(f"【全唐诗】《{title}》（{author}）\n{body}")
save("全唐诗.txt", records)
print(f"全唐诗原始 {total} 首，去重后 {len(records)} 首")
