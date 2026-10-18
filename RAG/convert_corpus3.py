# -*- coding: utf-8 -*-
"""第三批语料：全宋词 / 诗经 / 楚辞 → 知识库 txt。"""
import json, os, re

RAG = r"C:\Users\38107\Desktop\ai\RAG"
KB = r"C:\Users\38107\Desktop\ai\知识库"

def save(name, records):
    recs = [r.strip() for r in records if r.strip()]
    path = os.path.join(KB, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(recs) + "\n")
    print(f"{name}: {len(recs)} 条, {os.path.getsize(path)//1024} KB")

# 1. 全宋词（每首一条）
records = []
for fn in sorted(os.listdir(os.path.join(RAG, "song"))):
    if not fn.endswith(".json"):
        continue
    try:
        cis = json.load(open(os.path.join(RAG, "song", fn), encoding="utf-8"))
    except Exception as e:
        print("skip", fn, e); continue
    for c in cis:
        pai = c.get("rhythmic") or c.get("title") or "无名"
        author = c.get("author", "佚名")
        body = "".join(c.get("paragraphs", []))
        if body:
            records.append(f"【全宋词】《{pai}》（{author}）\n{body}")
save("全宋词.txt", records)

# 2. 诗经（每篇一条）
sj = json.load(open(os.path.join(RAG, "shijing.json"), encoding="utf-8"))
records = []
for p in sj:
    head = f"【诗经·{p['chapter']}·{p['section']}】《{p['title']}》"
    records.append(head + "\n" + "".join(p["content"]))
save("诗经.txt", records)

# 3. 楚辞（长篇按行分组切块，每块≤12行）
cc = json.load(open(os.path.join(RAG, "chuci.json"), encoding="utf-8"))
records = []
for p in cc:
    head = f"【楚辞·{p['section']}】《{p['title']}》（{p.get('author','屈原作者群')}）"
    lines = p["content"]
    for i in range(0, len(lines), 12):
        chunk = "".join(lines[i:i+12])
        tag = f"{head}（第{i//12+1}段）" if len(lines) > 12 else head
        records.append(tag + "\n" + chunk)
save("楚辞.txt", records)
