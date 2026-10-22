# -*- coding: utf-8 -*-
"""v1.4：超名篇反抄袭 + 事实问答 + 身份剧本 + v1.3全资产。"""
import json, os, re, random
from opencc import OpenCC
from imagery import IMAGERY, LINE_PATTERNS, ROLE_JUE, ROLE_LV, ADJ, LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, INSTR_TPL

random.seed(44)
cc = OpenCC("t2s")
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"
GENRE_FULL = {"五绝": "五言绝句", "七绝": "七言绝句", "五律": "五言律诗", "七律": "七言律诗"}

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
    kw = {"送": "送别", "思": "思念", "怀": "怀远", "咏": "咏物", "登": "登临"}.get(key, title[:2])
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=EMO_BY_KEY.get(key, "即景而生的一段深情远意"))

# ---- 新增原创（质检：字数/句数/韵部） ----
samples = []
n_ok, n_bad = 0, 0
for p in json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8")):
    units = p["u"]
    feet = [u[-1] for u in units[1::2]]
    parts = [char2rhyme.get(f) for f in feet]
    lens = set(len(u) for u in units)
    if (lens != {5} and lens != {7}) or len(units) not in (4, 8) or not all(parts) or not set.intersection(*parts):
        n_bad += 1
        print("淘汰:", p["t"], feet)
        continue
    for _ in range(2):
        body = "\n".join(units[i] + "，" + units[i+1] + "。" for i in range(0, len(units), 2))
        samples.append({"instruction": random.choice(INSTR_TPL).format(t=p["t"], g=GENRE_FULL[p["g"]]),
                        "input": "", "output": f"立意：{liyi(p['t'])}\n\n诗：\n《{p['t']}》\n{body}\n\n意象解释：\n{explain(units)}"})
    n_ok += 1
print("超名篇原创:", n_ok, "首 ×2，淘汰", n_bad)

# ---- 事实问答（常识，程序+手核） ----
FACTS = [
    ("平水韵一共有多少个韵部？", "平水韵共一百零六韵部：上平声十五部、下平声十五部、上声二十九部、去声三十部、入声十七部。作近体诗用韵，平声韵只在上平、下平三十部中取。"),
    ("平水韵是谁编的？", "平水韵因刊行者是南宋平水人刘渊而得名，其《壬子新刊礼部韵略》并为一百零七韵；今通行的一百零六韵本出自金代王文郁《平水新刊韵略》。二人皆与平水相关，故统称平水韵。"),
    ("平水韵的四声是什么？", "平水韵按平、上、去、入四声分部。平声又分上平、下平，只是卷次之分，并非两种声调；上、去、入三声为仄声。"),
    ("近体诗的押韵规则是什么？", "近体诗偶数句必须押韵，一般押平声韵，一韵到底；首句可入韵可不入韵，不入韵时首句末字用仄声。韵脚必须在同一韵部内（首句可借邻韵），不得出韵、混韵。"),
    ("律诗有几联？哪些联要对仗？", "律诗八句四联，依次为首联、颔联、颈联、尾联。颔联和颈联必须对仗，要求词性相对、结构相应；首尾两联可对可不对。"),
    ("绝句有几句？", "绝句四句，分五言绝句和七言绝句。绝句不要求对仗，但平仄和押韵仍须依格律：偶句押平声韵，一韵到底。"),
    ("什么是借邻韵？", "近体诗首句如不入本韵，可借用与本韵发音相近的邻韵字，称为借邻韵（孤雁出群格），只限首句；第二句起必须严守本韵。"),
    ("词林正韵是谁编的？有几部？", "《词林正韵》为清代戈载所编，把平上去三声分为十四部、入声分为五部，共十九部，是填词用韵的通行标准。它比平水韵宽，因词韵允许邻韵通押。"),
    ("词和诗的用韵有什么不同？", "诗依平水韵（一零六部，近体一韵到底）；词依词林正韵（十九部，可以邻韵通押），且按词牌指定位置押韵，可押平韵、仄韵或平仄转换。"),
    ("什么是平仄？", "平仄是汉语声调的两分：平声（阴平、阳平）为平，上声、去声、入声为仄。近体诗通过平仄在本句内的交替和对句间的相对，形成格律。"),
    ("什么是对仗？", "对仗指两句之间词性相对、结构相应、平仄相反：名词对名词、动词对动词、数词对数词。律诗颔联颈联必须对仗，忌合掌（两句意思重复）。"),
    ("五言和七言是什么意思？", "指诗句每句的字数：五言每句五字，七言每句七字。绝句四句，律诗八句；排律则十句以上，除首尾联外均须对仗。"),
]
for q, a in FACTS:
    samples.append({"instruction": q, "input": "", "output": a})
print("事实问答:", len(FACTS))

# ---- 身份剧本（最新版） ----
qa = json.load(open(os.path.join(TD, "qa_pilot.json"), encoding="utf-8"))
identity = [d for d in qa if any(k in d["instruction"] for k in ["创始人", "谁训练", "介绍一下你自己", "Quanzhi", "你是谁", "ChatGPT", "你是基于", "你能做什么", "你会写词", "作诗前", "知识库能查"])]
samples += identity
print("身份剧本:", len(identity))

# ---- v1.3 资产（去重：同 instruction+output 前缀视为重复） ----
v13 = json.load(open(os.path.join(TD, "poemly_sft_v13.json"), encoding="utf-8"))
# 剔除 v1.3 里的旧身份样本（避免与新版冲突）
old_ident = [d for d in v13 if any(k in d["instruction"] for k in ["你是谁", "ChatGPT", "你是基于", "你能做什么", "创始人"])]
v13 = [d for d in v13 if d not in old_ident]
print("v1.3 剔除旧身份:", len(old_ident))
# 新旧超名篇主题冲突：剔除 v1.3 中同题作诗样本（旧的是普通范本，新的才是诱饵专用）
new_titles = set()
for p in json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8")):
    new_titles.add(p["t"])
def conflicts(d):
    if "诗：\n《" not in d["output"]:
        return False
    m = re.search(r"诗：\n《(.+?)》", d["output"])
    return m and m.group(1) in new_titles
v13 = [d for d in v13 if not conflicts(d)]
seen = set((d["instruction"], d["output"][:60]) for d in samples)
for d in v13:
    k = (d["instruction"], d["output"][:60])
    if k not in seen:
        seen.add(k)
        samples.append(d)

random.shuffle(samples)
json.dump(samples, open(os.path.join(TD, "poemly_sft_v14.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("v1.4 总数:", len(samples))
