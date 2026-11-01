# -*- coding: utf-8 -*-
# =====================================================================
# 【本文件在管线中的作用】
#   poemly 训练数据工程 v1.5 版生成器 = v1.4 全部逻辑 + 三处升级：
#   ① EMO_BY_KEY 多原型兼容：镜像 imagery.py 的情感映射已改为"一键多原型"
#      列表，liyi() 用 random.choice 随机抽取——同题不同条的立意更多样；
#   ② 数据源扩容：originals_v14.json 由 4 首扩至 35 首（名题自作金标准）、
#      qa_pilot.json 扩至 18 条（身份+典故问答），关键映表新增 侠/剑/酒；
#   ③ 输出改名 poemly_sft_v15.json：保留 v1.4 数据集不动，供新旧模型对照。
#   其余板块（超名篇反抄袭、格律事实问答、身份剧本、v1.3 资产回收去重）
#   与 v1.4 完全一致。
# 【Python 特性速查（C 语言视角）】
#   import / from...import ≈ #include；dict ≈ 哈希表；list ≈ 动态数组
#   set()               ≈ 去重集合（本版用 set 字面量 {5} 做整集比较）
#   f"...{x}..."        ≈ sprintf；.format(...) ≈ 命名占位符版 sprintf
#   with open(...)      ≈ RAII；for x in xs ≈ 遍历；None ≈ NULL
#   [x for x in xs]     ≈ 列表推导式；(a, b) 元组可哈希，能当哈希键（≈ 结构体做键）
#   any()/all()         ≈ 短路求值的 OR/OF 聚合（找到即停，≈ 带 break 的循环）
#   a if cond else b    ≈ cond ? a : b；m and x ≈ 短路与（m 为 NULL 直接返回）
#   s[:60] / s[i:j]     ≈ 指针切片；re.search 全文找第一个匹配（re.match 只锚行首）
#   isinstance(x, list) ≈ 运行期类型检查（ unions 的老派写法，兼容新旧两种存法）
# 【执行前提】
#   1) 同目录 imagery.py、pip 安装 opencc；
#   2) "知识库"需有 平水韵字表.txt；
#   3) "训练数据"需有 originals_v14.json、qa_pilot.json、poemly_sft_v13.json。
#   运行方式：python gen_v15.py，产出 poemly_sft_v15.json。
# =====================================================================
"""v1.5：v1.4 逻辑 + EMO_BY_KEY 一键多原型；数据源扩容（originals 35 首 / qa 18 条）。"""
# 一行式文档字符串：本版自述
import json, os, re, random
# 4 个标准库：json 序列化、os 路径、re 正则、random 随机
from opencc import OpenCC
# 繁→简转换库
from imagery import IMAGERY, LINE_PATTERNS, ROLE_JUE, ROLE_LV, ADJ, LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, INSTR_TPL
# 自定义模块 imagery.py 的意象库/赏析句式/角色表/模板常量（≈ 数据头文件）

random.seed(44)
# 固定随机种子（≈srand(44)）：可复现
cc = OpenCC("t2s")
# 繁→简转换器对象
KB = r"C:\Users\38107\Desktop\ai\知识库"
# r"..." 原始字符串（反斜杠不转义）：知识库目录
TD = r"C:\Users\38107\Desktop\ai\训练数据"
# 训练数据目录
GENRE_FULL = {"五绝": "五言绝句", "七绝": "七言绝句", "五律": "五言律诗", "七律": "七言律诗"}
# 体裁简称→全称映射表

char2rhyme = {}
# "字→韵部集合"倒排索引：key=简体单字，value=所属平声韵部名集合（多音字可属多部）
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    # 逐行读韵表（文件对象可迭代，≈ while fgets；UTF-8 解码防乱码）
    m = re.match(r"平水韵·(上平|下平)声([一二三四五六七八九十]+)(.)（韵部收字", line)
    # 匹配平声韵部表头（近体诗只押平声韵，仄声部不入索引）
    if not m:
        # None（≈NULL）→ 非表头行
        continue
        # 跳过
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    # f-string 拼韵部全名，如"上平一东"
    chars = re.split(r"【詞】", re.sub(r"（[^（）]*）", "", line.split("：", 1)[1]))[0]
    # 取冒号后收字串 → 删括号内注释 → 按"【詞】"切分取前段（剔除词韵专用字）
    for c in chars:
        # 逐字符遍历
        if "\u4e00" <= c <= "\u9fff":
            # CJK 汉字码位判断，滤掉分隔符
            char2rhyme.setdefault(cc.convert(c), set()).add(name)
            # setdefault 无则建空集（≈ 查表插入），繁转简作键，韵部名入集合

NOIMG = ["\"{line}\"——{role}，写景如画，情在言外。", "\"{line}\"——句意{adj}，不假雕饰而韵味自出。", "\"{line}\"——此句{role}，平平道来，自有深致。"]
# 意象未命中时的兜底赏析句式数组（.format 占位符模板）

def find_img(line):
    # 在一句诗里找意象词，返回（词, 释义）或 (None, None)
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        # 按词长降序遍历（lambda≈qsort 回调，-len 倒序）：长词优先最长匹配
        if w in line:
            # 子串命中，≈ strstr != NULL
            return w, random.choice(imps if isinstance(imps, list) else [imps])
            # 随机释义；isinstance 兼容"释义是单串"的存法
    return None, None
    # 未命中返回双 NULL

def explain(units):
    # "逐句赏析"生成器：输入句元列表，输出逐句讲意象的赏析文本
    seq = units if len(units) == 4 else [units[i*2] + "，" + units[i*2+1] + "。" for i in range(4)]
    # 三目（≈ cond ? a : b）：绝句 4 句直接用；律诗 8 个半句两两拼成完整句（列表推导式）
    roles = ROLE_JUE if len(units) == 4 else ROLE_LV
    # 按体裁选角色表：绝句起承转合 / 律诗四联角色
    out = []
    # 赏析行容器
    for u, r in zip(seq, roles):
        # zip 按位置配对并行遍历句子与角色，每轮解包
        img, imp = find_img(u)
        # 本句查意象并解包
        out.append(random.choice(NOIMG).format(line=u, role=r, adj=random.choice(ADJ)) if img is None
                   else random.choice(LINE_PATTERNS).format(line=u, img=img, imp=imp, imp2=imp, role=r, adj=random.choice(ADJ)))
        # 本句赏析：img 为 NULL 用兜底句式，否则用意象精讲句式
    return "\n".join(out)
    # 换行串接成整段赏析

def liyi(title):
    # "立意"生成器：按诗题关键词推断题材与情感
    key = next((k for k in EMO_BY_KEY if k in title), None)
    # 取第一个出现在标题里的关键词，找不到给 None
    kw = {"送": "送别", "思": "思念", "怀": "怀远", "咏": "咏物", "登": "登临",
          "侠": "侠气", "剑": "剑气", "酒": "酒意"}.get(key, title[:2])
    # v1.5 关键词表在 v1.4 的 5 键上续增 侠/剑/酒；无命中用标题前两字
    # v1.5 兼容：EMO_BY_KEY 值已改为列表（一键多原型），random.choice 随机抽一条；
    # 仍是字符串的旧数据也能走通（isinstance 双保险）。
    pool = EMO_BY_KEY.get(key, EMO_DEFAULT)
    emo = random.choice(pool) if isinstance(pool, list) else pool
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=emo)
    # 随机立意模板；兜底情感词恢复引用 EMO_DEFAULT 常量（与 scale_generator 口径一致）

# ---- 新增原创（质检：字数/句数/韵部） ----
samples = []
# 总样本池（Alpaca 三字段哈希表的动态数组）
n_ok, n_bad = 0, 0
# 元组解包式双计数器：合格/淘汰
for p in json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8")):
    # 读入超名篇原创诗并在 for 头直接遍历（加载+迭代一步）
    units = p["u"]
    # 取句元数组
    feet = [u[-1] for u in units[1::2]]
    # 韵脚提取：步长切片取第 2、4、6、8 句（偶数句必押韵），负下标取末字
    parts = [char2rhyme.get(f) for f in feet]
    # 查每个韵脚的平声韵部集合
    lens = set(len(u) for u in units)
    # 各句字数收进 set：理想情况只剩一种长度
    if (lens != {5} and lens != {7}) or len(units) not in (4, 8) or not all(parts) or not set.intersection(*parts):
        # 四重质检：字数集合整集等于 {5} 或 {7}；句元数 4/8；韵脚全查到；
        # 韵部集合交集非空（同部一韵到底）。任一不过即淘汰
        n_bad += 1
        # 淘汰计数
        print("淘汰:", p["t"], feet)
        # 打印被淘汰的诗题与韵脚，便于人工复核
        continue
        # 跳过该诗
    for _ in range(2):
        # 每首 2 个指令变体；_ 为弃置循环变量
        body = "\n".join(units[i] + "，" + units[i+1] + "。" for i in range(0, len(units), 2))
        # 生成器表达式拼诗体：步长 2 两两组合"上句，下句。"再换行相连
        samples.append({"instruction": random.choice(INSTR_TPL).format(t=p["t"], g=GENRE_FULL[p["g"]]),
                        "input": "", "output": f"立意：{liyi(p['t'])}\n\n诗：\n《{p['t']}》\n{body}\n\n意象解释：\n{explain(units)}"})
        # 组装作诗样本：随机指令模板 + f-string 现场拼三段式答案
    n_ok += 1
    # 合格计数
print("超名篇原创:", n_ok, "首 ×2，淘汰", n_bad)
# 汇报合格数（每首 ×2 条样本）与淘汰数

# ---- 事实问答（常识，程序+手核） ----
FACTS = [
    # 事实问答库：每条是（问, 答）元组——格律硬知识，程序生成+人工核对
    ("平水韵一共有多少个韵部？", "平水韵共一百零六韵部：上平声十五部、下平声十五部、上声二十九部、去声三十部、入声十七部。作近体诗用韵，平声韵只在上平、下平三十部中取。"),
    # 知识点：平水韵 106 部的构成；近体诗只用平声 30 部
    ("平水韵是谁编的？", "平水韵因刊行者是南宋平水人刘渊而得名，其《壬子新刊礼部韵略》并为一百零七韵；今通行的一百零六韵本出自金代王文郁《平水新刊韵略》。二人皆与平水相关，故统称平水韵。"),
    # 知识点：平水韵得名与源流（刘渊 107 韵 → 王文郁 106 韵）
    ("平水韵的四声是什么？", "平水韵按平、上、去、入四声分部。平声又分上平、下平，只是卷次之分，并非两种声调；上、去、入三声为仄声。"),
    # 知识点：四声与平仄的对应；上平/下平只是分卷不是两种平声
    ("近体诗的押韵规则是什么？", "近体诗偶数句必须押韵，一般押平声韵，一韵到底；首句可入韵可不入韵，不入韵时首句末字用仄声。韵脚必须在同一韵部内（首句可借邻韵），不得出韵、混韵。"),
    # 知识点：偶句押平韵、一韵到底、首句可入韵可借邻韵
    ("律诗有几联？哪些联要对仗？", "律诗八句四联，依次为首联、颔联、颈联、尾联。颔联和颈联必须对仗，要求词性相对、结构相应；首尾两联可对可不对。"),
    # 知识点：律诗四联名称与对仗位置（中二联必须对仗）
    ("绝句有几句？", "绝句四句，分五言绝句和七言绝句。绝句不要求对仗，但平仄和押韵仍须依格律：偶句押平声韵，一韵到底。"),
    # 知识点：绝句形制——四句、不求对仗但守格律
    ("什么是借邻韵？", "近体诗首句如不入本韵，可借用与本韵发音相近的邻韵字，称为借邻韵（孤雁出群格），只限首句；第二句起必须严守本韵。"),
    # 知识点：孤雁出群格——仅首句可用邻韵
    ("词林正韵是谁编的？有几部？", "《词林正韵》为清代戈载所编，把平上去三声分为十四部、入声分为五部，共十九部，是填词用韵的通行标准。它比平水韵宽，因词韵允许邻韵通押。"),
    # 知识点：词韵 19 部与编者；词韵比诗韵宽
    ("词和诗的用韵有什么不同？", "诗依平水韵（一零六部，近体一韵到底）；词依词林正韵（十九部，可以邻韵通押），且按词牌指定位置押韵，可押平韵、仄韵或平仄转换。"),
    # 知识点：诗韵与词韵的核心差异（部数/通押/韵位）
    ("什么是平仄？", "平仄是汉语声调的两分：平声（阴平、阳平）为平，上声、去声、入声为仄。近体诗通过平仄在本句内的交替和对句间的相对，形成格律。"),
    # 知识点：平仄二分与句内交替、对句相对的格律机制
    ("什么是对仗？", "对仗指两句之间词性相对、结构相应、平仄相反：名词对名词、动词对动词、数词对数词。律诗颔联颈联必须对仗，忌合掌（两句意思重复）。"),
    # 知识点：对仗三要素与"合掌"之忌
    ("五言和七言是什么意思？", "指诗句每句的字数：五言每句五字，七言每句七字。绝句四句，律诗八句；排律则十句以上，除首尾联外均须对仗。"),
    # 知识点：五言/七言的定义与排律常识
]
for q, a in FACTS:
    # 遍历问答库，每轮元组解包出问句 q 与答案 a
    samples.append({"instruction": q, "input": "", "output": a})
    # 直接组装成 Alpaca 样本（无随机成分，问答内容固定）
print("事实问答:", len(FACTS))
# 汇报事实问答条数

# ---- 身份剧本（最新版） ----
qa = json.load(open(os.path.join(TD, "qa_pilot.json"), encoding="utf-8"))
# 读入人工编写的人设问答底稿
identity = [d for d in qa if any(k in d["instruction"] for k in ["创始人", "谁训练", "介绍一下你自己", "Quanzhi", "你是谁", "ChatGPT", "你是基于", "你能做什么", "你会写词", "作诗前", "知识库能查"])]
# 列表推导式 + any() 短路筛选：指令里出现任一关键词即视为"身份剧本"样本
samples += identity
# 新版身份剧本入池
print("身份剧本:", len(identity))
# 汇报

# ---- v1.3 资产（去重：同 instruction+output 前缀视为重复） ----
v13 = json.load(open(os.path.join(TD, "poemly_sft_v13.json"), encoding="utf-8"))
# 读入上一版 v1.3 数据集准备回收
# 剔除 v1.3 里的旧身份样本（避免与新版冲突）
old_ident = [d for d in v13 if any(k in d["instruction"] for k in ["你是谁", "ChatGPT", "你是基于", "你能做什么", "创始人"])]
# 同样按关键词筛出旧版身份剧本——旧答案可能已过时，保留会与新剧本互相矛盾
v13 = [d for d in v13 if d not in old_ident]
# 重建列表剔除旧身份样本
print("v1.3 剔除旧身份:", len(old_ident))
# 汇报剔除数量
# 新旧超名篇主题冲突：剔除 v1.3 中同题作诗样本（旧的是普通范本，新的才是诱饵专用）
new_titles = set()
# 空集合：收集本版超名篇原创的诗题（哈希集合，O(1) 查询）
for p in json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8")):
    # 再读一遍 originals_v14.json（重复读文件换取代码简洁）
    new_titles.add(p["t"])
    # 诗题入集合
def conflicts(d):
    # 判断一条旧样本是否与本版超名篇主题冲突
    if "诗：\n《" not in d["output"]:
        # 非作诗样本（没有"诗：\n《"标记）不冲突
        return False
        # 直接否
    m = re.search(r"诗：\n《(.+?)》", d["output"])
    # re.search 全文找第一个"《诗题》"；(.+?) 非贪婪
    return m and m.group(1) in new_titles
    # and 短路：m 为 NULL 返回 None（假值），否则返回"诗题是否在冲突名单"的布尔
v13 = [d for d in v13 if not conflicts(d)]
# 过滤：同题旧作诗样本剔除——同一题目只保留本版"诱饵专用"新答案
seen = set((d["instruction"], d["output"][:60]) for d in samples)
# 建已见指纹集合：指纹=(指令, 答案前 60 字) 的二元组——宽容去重（前缀相同即视为重复）
for d in v13:
    # 逐条检查 v1.3 剩余样本
    k = (d["instruction"], d["output"][:60])
    # 算指纹
    if k not in seen:
        # 指纹没见过
        seen.add(k)
        # 登记指纹
        samples.append(d)
        # 入池
# —— 经典哈希去重循环：防同一问答在新旧版本里重复出现，训练集更干净

random.shuffle(samples)
# 总池最后洗牌：样本顺序随机化
json.dump(samples, open(os.path.join(TD, "poemly_sft_v15.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 序列化写盘：中文原样输出（ensure_ascii=False）、indent=1 便于 diff
print("v1.5 总数:", len(samples))
# 汇报最终规模
