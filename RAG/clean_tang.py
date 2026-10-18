# -*- coding: utf-8 -*-
"""清洗全唐诗语料：去校勘注（[X]（Y）→X、长圆括号按语、〖〗注、★□等），重建 全唐诗.txt。"""
import os, re
from opencc import OpenCC

KB = r"C:\Users\38107\Desktop\ai\知识库"
cc = OpenCC("t2s")

text = open(os.path.join(KB, "全唐诗.txt"), encoding="utf-8").read()
records = [r.strip() for r in text.split("\n\n") if r.strip()]
print("清洗前:", len(records), "条")

def clean_rec(rec):
    head, _, body = rec.partition("\n")
    # 长圆括号按语（校勘说明，>10字符）整段删除；短括号（如（无名氏）、（借邻韵））保留
    body = re.sub(r"（[^（）]{10,}）", "", body)
    # [X]（Y）→ X ；孤立的 [X] 保留 X
    body = re.sub(r"\[([^\[\]]{1,2})\]（[^（）]*）", r"\1", body)
    body = re.sub(r"\[([^\[\]]{1,2})\]", r"\1", body)
    # 〖...〗 校注块整删
    body = re.sub(r"〖[^〖〗]*〗", "", body)
    # 残留符号
    body = body.replace("★", "").replace("□", "").replace("○", "")
    body = re.sub(r"[ \t]{2,}", " ", body).strip()
    return head + "\n" + body if body else head

out = []
for r in records:
    c = clean_rec(r)
    # 过滤：正文过短的（清完只剩标题的残片）
    body = c.partition("\n")[2]
    if len(re.sub(r"[^\u4e00-\u9fff]", "", body)) >= 10:
        out.append(c)

path = os.path.join(KB, "全唐诗.txt")
open(path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
print("清洗后:", len(out), "条,", os.path.getsize(path) // 1024 // 1024, "MB")
print("样例:", out[52880 % len(out)][:80].replace("\n", " | "))
