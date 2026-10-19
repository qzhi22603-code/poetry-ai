# -*- coding: utf-8 -*-
"""扩产引擎：真诗为骨 + 意象词典解释 + 金标准锚定 → poemly_sft_v1.json（约3000条）。
全部样本过质检：字数/句数/韵部/收尾纪律。
"""
import json, os, re, random, hashlib
from collections import Counter
from opencc import OpenCC
from imagery import IMAGERY, LINE_PATTERNS, ROLE_JUE, ROLE_LV, ADJ, LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, INSTR_TPL

random.seed(2026)
cc = OpenCC("t2s")
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"

# ---------- 平水韵 ----------
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

def rhyme_ok(sent):
    feet = [re.sub(r"[^\u4e00-\u9fff]", "", s)[-1] for s in sent[1::2]]
    parts = [char2rhyme.get(f) for f in feet]
    if not parts or any(p is None for p in parts):
        return False
    return bool(set.intersection(*parts))

# ---------- 语料字频（韵部问答用） ----------
freq = Counter()
for fn in ["唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt", "全宋词.txt"]:
    p = os.path.join(KB, fn)
    if os.path.exists(p):
        freq.update(c for c in open(p, encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")

# ---------- 解析范诗 ----------
FAMOUS = set("李白 杜甫 王维 孟浩然 白居易 李商隐 杜牧 刘禹锡 柳宗元 韦应物 岑参 高适 王昌龄 王之涣 贾岛 姚合 钱起 刘长卿 卢纶 韩翃 司空曙 韩愈 孟郊 张籍 王建 元稹 温庭筠 韦庄 杜荀鹤 许浑 罗隐 陆龟蒙 皮日休 崔颢 祖咏 常建 刘方平 张祜 朱庆馀 郑谷 韦应物 戴叔伦 皇甫冉 郎士元 畅当 裴迪 王翰 王湾 张九龄".split())

def parse_file(fn, source):
    out = []
    text = open(os.path.join(KB, fn), encoding="utf-8").read()
    for rec in text.split("\n\n"):
        m = re.match(r"【[^】]+】《(.+?)》（(?:([^·）]*)·)?([^）]*)）\n(.+)", rec.strip(), re.S)
        if not m:
            continue
        title, _, author, body = m.groups()
        out.append((title, author, body.strip()))
    return out

poems_all = parse_file("唐诗三百首.txt", "ts") + parse_file("千家诗.txt", "qjs")

# 全唐诗按名作家抽样
seen_body, tang = set(), []
for rec in open(os.path.join(KB, "全唐诗.txt"), encoding="utf-8").read().split("\n\n"):
    m = re.match(r"【全唐诗】《(.+?)》（(.+?)）\n(.+)", rec.strip(), re.S)
    if not m:
        continue
    title, author, body = m.groups()
    if author not in FAMOUS:
        continue
    h = hashlib.md5(body.encode()).hexdigest()
    if h in seen_body:
        continue
    seen_body.add(h)
    tang.append((title, author, body.strip()))
random.shuffle(tang)

def classify(body):
    """返回 (体裁名, [句]) 或 None。"""
    units = [u.strip() for u in re.split(r"[，。？！]", body) if u.strip()]
    if len(units) in (4, 8) and units and len(set(len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units)) == 1:
        n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
        if n in (5, 7) and all(re.fullmatch(r"[\u4e00-\u9fff]+", u) for u in units):
            g = ("五言绝句" if n == 5 else "七言绝句") if len(units) == 4 else ("五言律诗" if n == 5 else "七言律诗")
            return g, units
    return None

def find_imagery(line):
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        if w in line:
            opts = imps if isinstance(imps, list) else [imps]
            return w, random.choice(opts)
    return None, None

KEY2WORD = {"送": "送别", "别": "离别", "思": "思念", "怀": "怀远", "咏": "咏物",
            "边": "边塞", "塞": "边塞", "归": "归乡", "书": "读书", "夜": "夜坐",
            "村": "田家", "田": "田家", "春": "春景", "秋": "秋景", "冬": "冬日", "夏": "夏日"}

def make_liyi(title):
    key = next((k for k in EMO_BY_KEY if k in title), None)
    emo = EMO_BY_KEY.get(key, EMO_DEFAULT)
    kw = KEY2WORD.get(key, title[:2])
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=emo)

NOIMG_PATTERNS = [
    "\"{line}\"——{role}，写景如画，情在言外。",
    "\"{line}\"——句意{adj}，不假雕饰而韵味自出。",
    "\"{line}\"——此句{role}，平平道来，自有深致。",
]

_used = set()
def explain_unit(u, role):
    for _ in range(6):
        img, imp = find_imagery(u)
        if img is None:
            s = random.choice(NOIMG_PATTERNS).format(line=u, role=role, adj=random.choice(ADJ))
        else:
            s = random.choice(LINE_PATTERNS).format(
                line=u, img=img, imp=imp, imp2=imp, role=role, adj=random.choice(ADJ))
        if s not in _used:
            _used.add(s)
            return s
    return s

def make_explanation(units):
    if len(units) == 4:
        return "\n".join(explain_unit(u, ROLE_JUE[i]) for i, u in enumerate(units))
    return "\n".join(
        explain_unit(units[i * 2] + "，" + units[i * 2 + 1] + "。", ROLE_LV[i])
        for i in range(4))

samples = []
def add_poem(title, author, units, genre):
    instr = random.choice(INSTR_TPL).format(t=title, g=genre)
    body = "\n".join(units[i] + ("，" if i % 2 == 0 else "。") + (units[i + 1] + "。" if i % 2 == 0 else "") for i in range(0, len(units), 2))
    output = f"立意：{make_liyi(title)}\n\n诗：\n《{title}》\n{body}\n\n意象解释：\n{make_explanation(units)}"
    samples.append({"instruction": instr, "input": "", "output": output, "_src": f"{author}"})

count_by_genre = Counter()
PLAN = {"五言绝句": 500, "七言绝句": 500, "五言律诗": 450, "七言律诗": 450}
def feed(pool):
    for title, author, body in pool:
        if all(count_by_genre[g] >= v for g, v in PLAN.items()):
            return
        cls = classify(body)
        if not cls:
            continue
        g, units = cls
        if count_by_genre[g] >= PLAN[g] or not rhyme_ok(units):
            continue
        if re.search(r"[五六七]言|绝句|律诗|排律|长句|杂言", title):
            continue  # 题目自带体裁字样，避免与指令矛盾
        count_by_genre[g] += 1
        add_poem(title, author, units, g)

feed(poems_all)
feed(tang)
print("作诗样本:", sum(count_by_genre.values()), dict(count_by_genre))

# ---------- 韵部问答（扩至 240） ----------
yun_words = [w for w in freq if len(w) == 1 and char2rhyme.get(w) and freq[w] >= 200]
random.shuffle(yun_words)
yun_qa = []
for w in yun_words:
    if len(yun_qa) >= 270:
        break
    names = sorted(char2rhyme[w])
    name = names[0]
    same = [c for c in char2rhyme if c != w and name in char2rhyme[c] and freq.get(c, 0) >= 30]
    same.sort(key=lambda c: -freq.get(c, 0))
    if len(same) < 8:
        continue
    show = "、".join(same[:16])
    qi = random.choice([
        f"「{w}」字在平水韵中属哪个韵部？同部还有哪些常用字？",
        f"作近体诗时用「{w}」作韵脚，其余韵脚应用什么字？",
        f"「{w}」押平水韵哪一部？请列举同部常用字。",
    ])
    ao = (f"「{w}」属平水韵【{name}】部。同部常用韵字有：{show}等。"
          f"作近体诗时，韵脚须与此部字相押（首句可借邻韵），不可出韵。")
    yun_qa.append({"instruction": qi, "input": "", "output": ao, "_src": "韵表生成"})
print("韵部问答:", len(yun_qa))

# ---------- 名句出处问答（300） ----------
src_pool = parse_file("唐诗三百首.txt", "ts") + parse_file("宋词三百首.txt", "sc") + parse_file("千家诗.txt", "qj")
random.shuffle(src_pool)
src_qa = []
for title, author, body in src_pool:
    if len(src_qa) >= 400:
        break
    first = body.split("。")[0].strip()
    if len(first) < 6 or len(first) > 40:
        continue
    is_ci = "词" in author or len(re.sub(r"[^\u4e00-\u9fff]", "", first.split("，")[0])) not in (5, 7)
    kind = "哪首词" if is_ci else "哪首诗"
    src_qa.append({
        "instruction": f"「{first}」出自{kind}？",
        "input": "",
        "output": f"出自{author}的《{title}》：\n{body}",
        "_src": "出处生成"})
print("出处问答:", len(src_qa))

# ---------- 体裁辨识（250） ----------
meter_qa = []
pool2 = poems_all + tang[:400]
random.shuffle(pool2)
for title, author, body in pool2:
    if len(meter_qa) >= 480:
        break
    cls = classify(body)
    if not cls:
        continue
    g, units = cls
    n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
    excerpt = units[0] + "，" + units[1] + "。"
    qi = random.choice([
        f"「{excerpt}」每句几个字？是五言还是七言？",
        f"判断下面诗句的体裁字数：「{excerpt}」",
    ])
    ao = f"每句{n}字，是{'五言' if n == 5 else '七言'}；全诗为{g}（共{len(units)}句）。作此体裁时每句必须恰{n}字。"
    meter_qa.append({"instruction": qi, "input": "", "output": ao, "_src": "体裁辨识"})
print("体裁辨识:", len(meter_qa))

# ---------- 合并金标准 + 典故/身份 ----------
gold = json.load(open(os.path.join(TD, "poems_pilot.json"), encoding="utf-8"))
qa = json.load(open(os.path.join(TD, "qa_pilot.json"), encoding="utf-8"))
for d in gold + qa:
    d["_src"] = "手写金标准"

ident_extra = [
    {"instruction": "请介绍一下你自己", "input": "", "output": "我是 poemly，主人的诗词创作助手。我能作五言七言、绝句律诗，用韵必依平水韵，先立意后成篇，写完逐联解意象；也能查典故出处、检索范作、讲论词话诗话。"},
    {"instruction": "你会写词吗？", "input": "", "output": "会。词依词林正韵，按词牌句读填词。若你指定词牌（如《浣溪沙》《鹧鸪天》），我按其格律填写，并说明所押词韵。"},
    {"instruction": "作诗前你为什么总要先说立意？", "input": "", "output": "先立意是我的本分：动笔前确定主题与情感方向，围绕立意选意象、安排章法，诗才能情景交融、脉络贯通。这不需你操心，我自会如此作答。"},
    {"instruction": "你的知识库能查到什么？", "input": "", "output": "我备有平水韵、词林正韵字表，全唐诗、全宋词及唐诗宋词三百首、千家诗，诗经、楚辞，声律启蒙、笠翁对韵、幼学琼林、龙文鞭影，人间词话、沧浪诗话。查韵部、找范作、核典故出处都可依赖实据，不作无据之谈。"},
]
for d in ident_extra:
    d["_src"] = "手写金标准"

data = gold + qa + ident_extra + samples + yun_qa + src_qa + meter_qa
print("合并总数:", len(data))

# ---------- 全量质检 ----------
errors = []
for i, d in enumerate(data):
    out = d["output"]
    if "诗：\n《" in out:
        m2 = re.search(r"诗：\n《(.+?)》\n(.+)", out, re.S)
        title, body = m2.groups()
        units = [u for u in re.split(r"[，。？！]", body.split("\n\n意象解释")[0]) if u.strip()]
        lens = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units]
        if len(set(lens)) != 1 or lens[0] not in (5, 7):
            errors.append(f"[{i}]{title}句长{lens}")
        elif len(units) not in (4, 8):
            errors.append(f"[{i}]{title}句数{len(units)}")
        elif not rhyme_ok(units):
            feet = "".join(re.sub(r"[^\u4e00-\u9fff]", "", u)[-1] for u in units[1::2])
            errors.append(f"[{i}]{title}韵脚{feet}")
        last = [l for l in out.splitlines() if l.strip()][-1]
        if re.match(r"^(以上|总之|希望|如有)", last.strip()):
            errors.append(f"[{i}]{title}客套收尾")
    if "以上便是" in out or "希望你喜欢" in out:
        errors.append(f"[{i}]客套语")

bad = set(int(e.split("]")[0][1:]) for e in errors)
data = [d for i, d in enumerate(data) if i not in bad]
print("质检剔除:", len(bad), "条；最终:", len(data), "条")

for d in data:
    d.pop("_src", None)
json.dump(data, open(os.path.join(TD, "poemly_sft_v1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已写出 poemly_sft_v1.json")
