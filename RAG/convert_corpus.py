# -*- coding: utf-8 -*-
"""把下载的原始语料统一整理成知识库 txt：一条记录 = 一段空行隔开的文本。"""
import json, re, os
from opencc import OpenCC

RAG = r"C:\Users\38107\Desktop\ai\RAG"
KB = r"C:\Users\38107\Desktop\ai\知识库"
os.makedirs(KB, exist_ok=True)
cc = OpenCC("t2s")

def save(name, records, to_simplified=True):
    recs = [cc.convert(r) if to_simplified else r for r in records]
    recs = [r.strip() for r in recs if r.strip()]
    path = os.path.join(KB, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(recs) + "\n")
    print(f"{name}: {len(recs)} 条, {os.path.getsize(path)} 字节")

# 1&2. 唐诗三百首 / 千家诗
def flatten_paragraphs(paras):
    out = []
    for x in paras:
        if isinstance(x, dict):
            sub = cc.convert(x.get("subchapter") or "")
            for s in x["paragraphs"]:
                out.append((sub + "　" if sub else "") + cc.convert(s))
        else:
            out.append(cc.convert(x))
    return "".join(out)

def poems(jsonfile, out, bookname):
    d = json.load(open(os.path.join(RAG, jsonfile), encoding="utf-8"))
    records = []
    for juan in d["content"]:
        genre = juan.get("type", "")
        for p in juan["content"]:
            head = f"《{cc.convert(p['chapter'])}》"
            who = cc.convert(p.get("author") or "佚名")
            tag = f"（{cc.convert(genre)}·{who}）" if genre else f"（{who}）"
            body = flatten_paragraphs(p["paragraphs"])
            records.append(f"【{bookname}】{head}{tag}\n{body}")
    save(out, records, to_simplified=False)

poems("tangshisanbaishou.json", "唐诗三百首.txt", "唐诗三百首")
poems("qianjiashi.json", "千家诗.txt", "千家诗")

# 3. 声律启蒙：每段一条
d = json.load(open(os.path.join(RAG, "shenglvqimeng.json"), encoding="utf-8"))
records = []
for juan in d["content"]:
    for ch in juan["content"]:
        chap = cc.convert(ch["chapter"]).replace(" ", "")
        for para in ch["paragraphs"]:
            records.append(f"【声律启蒙·{chap}】\n{cc.convert(para)}")
save("声律启蒙.txt", records, to_simplified=False)

# 4. 幼学琼林：每段一条（典故库）
d = json.load(open(os.path.join(RAG, "youxueqionglin.json"), encoding="utf-8"))
records = []
for juan in d["content"]:
    for ch in juan["content"]:
        chap = cc.convert(ch["chapter"])
        for para in ch["paragraphs"]:
            records.append(f"【幼学琼林·{chap}】\n{cc.convert(para)}")
save("幼学琼林.txt", records, to_simplified=False)

# 5. 宋词三百首：词牌/作者/词文 三元组
text = open(os.path.join(RAG, "songci300.txt"), encoding="utf-8").read()
records = []
cur = {}
for line in text.splitlines():
    line = line.strip()
    if line.startswith("词牌:") or line.startswith("詞牌:"):
        cur = {"t": line.split(":", 1)[1]}
    elif (line.startswith("作者:") or line.startswith("作者:")) and "t" in cur:
        cur["a"] = line.split(":", 1)[1]
    elif (line.startswith("词文:") or line.startswith("詞文:")) and "t" in cur:
        body = line.split(":", 1)[1].replace("○", "　／　").replace("★", "□")
        records.append(f"《{cc.convert(cur['t'])}》{cc.convert(cur.get('a', '佚名'))}\n{cc.convert(body)}")
        cur = {}
save("宋词三百首.txt", records, to_simplified=False)

# 6. 平水韵字表：保留繁体原文（避免简繁转换破坏韵字归部）
text = open(os.path.join(RAG, "pingshui-raw.txt"), encoding="utf-8").read()
records = []
cur_name, cur_chars = None, []
for line in text.splitlines():
    m = re.match(r"^(上平|下平|上|去|入)聲([一二三四五六七八九十百]+)\{\{\+\+\|(.+?)\}\}", line.strip())
    if m:
        if cur_name:
            records.append(cur_name + "：" + "".join(cur_chars))
        sheng, num, zi = m.groups()
        cur_name = f"平水韵·{sheng}声{num}{zi}（韵部收字，末尾【词】为词韵增字）"
        cur_chars = []
    elif cur_name and line.strip() and not line.startswith("==") and not line.startswith("{{"):
        cur_chars.append(line.strip())
if cur_name:
    records.append(cur_name + "：" + "".join(cur_chars))
save("平水韵字表.txt", records, to_simplified=False)

# 7. 笠翁对韵：维基文库 30 页
import pickle
pkl = os.path.join(RAG, "liweng-pages.pkl")
if os.path.exists(pkl):
    pages = pickle.load(open(pkl, "rb"))
    records = []
    for page in pages:
        m = re.search(r"\|\s*section\s*=\s*(\S+)", page)
        sect = cc.convert(m.group(1)) if m else "?"
        body = []
        for line in page.splitlines():
            line = line.strip().lstrip(":").strip().replace("\u3000", "")
            if not line or line.startswith("{{") or line.startswith("==") or line.startswith("[["):
                continue
            if re.fullmatch(r"[\u4e00-\u9fff，。、；：？！·（）]+", line):
                body.append(cc.convert(line))
        if body:
            records.append(f"【笠翁对韵·{sect}】\n" + "".join(body))
    save("笠翁对韵.txt", records, to_simplified=False)
else:
    print("笠翁对韵: pkl 未就绪，跳过")
