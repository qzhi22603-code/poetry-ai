# -*- coding: utf-8 -*-
# ==============================================================================
# 【本文件在管线中的作用】
#   这是 poemly 的"数据规模化生成器"（扩产引擎）：把知识库里的真诗、平水韵表、
#   语料字频，经"筛选→组装→质检"流水线，批量产出约 3000 条 SFT 微调样本，
#   最终落盘为 训练数据\poemly_sft_v1.json。全脚本分七步：
#     ① 建平水韵字表（韵脚校验用）+ 语料字频表（挑高频字出题用）；
#     ② 解析唐诗三百首/千家诗/全唐诗名家篇，判体裁、验押韵，组装"作诗样本"；
#     ③ 生成"韵部问答"样本（某字属哪部、同部字有哪些）；
#     ④ 生成"名句出处"问答样本；
#     ⑤ 生成"体裁辨识"（五言/七言）问答样本；
#     ⑥ 并入手写金标准与"身份认知"样本，打溯源标记 _src；
#     ⑦ 全量质检（字数/句数/韵脚/客套收尾），剔除坏样本，写 JSON 交付。
#   意象词表与模板来自同目录 imagery.py——数据工程的"原料"与"车间"两个文件。
#
# 【Python 特性速查（C 语言视角）】
#   - import ≈ #include，但发生在运行期；json/os/re/random/hashlib/collections
#     是标准库模块，opencc 是第三方库。
#   - dict ≈ 哈希表；list ≈ 动态数组；set ≈ 哈希集合（去重 + O(1) 查询）；
#     tuple（元组）≈ 不可变小结构体，常打包多值返回，再"解包"赋给多个变量。
#   - f-string / str.format ≈ sprintf；"\n".join(数组) ≈ 循环 strcat；
#     字符串是不可变对象，所有"拼接"都在生成新串。
#   - 列表/字典/生成器推导式 [x for x in xs if 条件] ≈ 循环构建数组的语法糖。
#   - open(file, encoding="utf-8") 打开文件；本脚本未显式 close（脚本进程退出即
#     回收句柄），规范写法是 with（≈RAII，作用域结束自动释放）。
#   - random.seed(n) ≈ srand(n)：固定种子保证数据可复现；choice ≈ 等概率取一元素，
#     shuffle ≈ Fisher-Yates 洗牌。
#   - None ≈ NULL；dict.get(键) 查不到返回 None（下标取值则抛异常）；
#     lambda ≈ 内联匿名函数；切片 s[a:b] / s[::2] / s[-1] ≈ 指针运算的语法糖。
#
# 【执行前提】
#   - 需安装第三方库 OpenCC（如 pip install opencc-python-reimplemented）做繁→简转换。
#   - 知识库目录 KB 下需有：平水韵字表.txt、唐诗三百首.txt、千家诗.txt、
#     宋词三百首.txt、全宋词.txt、全唐诗.txt（缺失部分会跳过，见各处容错）。
#   - 训练数据目录 TD 下需有 poems_pilot.json、qa_pilot.json（手写金标准）。
#   - 需与 imagery.py 同目录。随机种子固定为 2026，重复运行产出一致，可回归验证。
# ==============================================================================
# 模块文档字符串（docstring）：三引号跨行字符串（下面三行是一个整体！），存进 __doc__；
# 注意它不是注释——里面是字符串内容，任何插入都会变成数据，所以注释只能加在它外面。
"""扩产引擎：真诗为骨 + 意象词典解释 + 金标准锚定 → poemly_sft_v1.json（约3000条）。
全部样本过质检：字数/句数/韵部/收尾纪律。
"""
# 一行导入 5 个标准库模块（≈5 个 #include 合一行）：json=JSON 读写、os=路径与文件、
# re=正则表达式、random=伪随机数、hashlib=MD5 摘要（这里拿来做诗句去重指纹）。
import json, os, re, random, hashlib
# 从标准库 collections 导入 Counter：一个"计数字典"（键→出现次数），
# 等价于自己开哈希表写 cnt[key]++，这里用于统计汉字频率和体裁配额。
from collections import Counter
# 导入第三方库 OpenCC 并在下一行实例化：做繁→简中文转换——平水韵字表是繁体，
# 必须转成简体才能和简体诗句对上键，否则韵表查询全落空（数据对齐的关键一步）。
from opencc import OpenCC
# 从同目录 imagery.py 导入全部词表与模板——两个文件的接口只有这一行，
# 相当于 extern 引入另一编译单元的常量表；这些名字在后面被反复查表。
from imagery import IMAGERY, LINE_PATTERNS, ROLE_JUE, ROLE_LV, ADJ, LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, INSTR_TPL

# 固定随机数种子：让 random 全系列（choice/shuffle/…）每次运行产生同一序列（≈srand）。
# 数据工程铁律——可复现性：换一天重跑数据集逐字节一致，才能做回归与对照实验。
random.seed(2026)
# 创建繁→简转换器对象（"t2s"=Traditional to Simplified）；Python 对象≈"malloc 的
# 结构体+绑定函数"，cc.convert(字) 就是调用它的方法，后面逐字转换韵表用。
cc = OpenCC("t2s")
# 知识库目录常量。r"..." 是"原始字符串"（raw string）：反斜杠不当转义符，
# 等价于 C 里写 "C:\\Users\\..." 的双反斜杠——Windows 路径必备写法。
KB = r"C:\Users\38107\Desktop\ai\知识库"
# 训练数据目录常量（同上用原始字符串），最终 JSON 数据集将写到这里。
TD = r"C:\Users\38107\Desktop\ai\训练数据"

# ---------- 平水韵 ----------
# 新建空字典（空哈希表）：键=单个汉字，值=该字所属韵部名集合——
# 这是全管线"押韵校验"的核心数据结构，下面对着韵表文件逐行填它。
char2rhyme = {}
# 打开平水韵字表并逐行迭代：for 直接遍历文件对象=逐行读（每行含结尾 \n），
# 相当于 C 的 while(fgets)；没显式 close 属脚本级偷懒，进程退出即回收。
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    # 正则从行首匹配"韵部标题行"：组1=上平/下平，组2=韵目（汉字数字），
    # 组3=韵目代表字。re.match 只锚定开头（≈strncmp 前缀比对+sscanf 提取），
    # 匹配失败返回 None（≈NULL）。
    m = re.match(r"平水韵·(上平|下平)声([一二三四五六七八九十]+)(.)（韵部收字", line)
    # not m：Python 真值判断中 None 视为假——不是韵部标题行就 continue 跳过，
    # 进入文件下一行（continue 语义与 C 相同）。
    if not m:
        continue
    # f-string ≈ sprintf：把正则捕获组拼成"上平一东"这类韵部名——
    # f 前缀表示花括号内是"现算的表达式"，比 format 更直白。
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    # 这行做三层文本清洗（链式调用=外层函数吃内层函数的返回值）：
    # ① line.split("：", 1) 按全角冒号最多切 1 刀，[1] 取冒号后的韵字串（下标从 0 起）；
    # ② re.sub 把括号小注（如"（又音X）"）整段删成空串，避免注字混进韵字表；
    # ③ re.split(r"【詞】", ...) 按"【詞】"标记切开、[0] 取前半——留下纯韵字区。
    chars = re.split(r"【詞】", re.sub(r"（[^（）]*）", "", line.split("：", 1)[1]))[0]
    # 遍历字符串：Python 的 str 可迭代，每次 c 得到长度为 1 的子串（不是 C 的 char 整数）。
    for c in chars:
        # 用 Unicode 码点区间过滤汉字（\u4e00~\u9fff 是 CJK 统一表意区）；
        # 字符串可直接比大小（比码点），相当于 C 里比较 wchar_t。
        if "\u4e00" <= c <= "\u9fff":
            # 两步并一行：setdefault(简体字, 空set) ——键不存在则插入空集合并返回它
            # （"取到或建好"的原子写法），再 .add(name) 把韵部名挂进该字的集合。
            # 值用 set（哈希集合）是因为一字可属多个韵部且天然去重；
            # cc.convert(c) 先把繁体转简体再做键——与简体语料对齐。
            char2rhyme.setdefault(cc.convert(c), set()).add(name)

# 定义"押韵是否合格"的校验函数：def 声明函数（无需写返回类型，参数无类型标注）；
# 形参 sent 约定为"拆好的句子元组/列表"（绝句 4 句、律诗 8 句）。
def rhyme_ok(sent):
    # 列表推导式=循环建数组的语法糖：sent[1::2] 是切片"从下标 1 起每隔一个取一个"，
    # 即第 2、4（、6、8）句——近体诗偶数句必须押韵；对每句先 re.sub 剥掉所有非汉字，
    # 再取 [-1]（负下标=从尾数第一）得韵脚字——feet 即全部韵脚数组。
    feet = [re.sub(r"[^\u4e00-\u9fff]", "", s)[-1] for s in sent[1::2]]
    # 对每个韵脚字查韵部表：dict.get(键) 查不到返回 None（≈NULL）而不抛异常，
    # 正好利用 None 表达"此字不在韵表"。
    parts = [char2rhyme.get(f) for f in feet]
    # not parts：连韵脚都没有（空数组为假）；any(...)：存在任一韵脚查不到韵部
    # （p is None 用 is 判"同一性"，≈p==NULL 的规范写法）——任一不成立即押韵失败。
    if not parts or any(p is None for p in parts):
        return False
    # 集合求交集：*parts 把列表"拆包"成多个实参（变长传参，≈把数组摊给变参函数）；
    # 交集非空=所有韵脚至少同属一个韵部→押韵成立；bool() 把空/非空集合转真/假。
    return bool(set.intersection(*parts))

# ---------- 语料字频（韵部问答用） ----------
# 新建计数字典：键=汉字，值=全部语料中的出现次数——后面挑"高频字"出韵部题用。
freq = Counter()
# 遍历 4 个语料文件名的列表字面量（动态数组初始化）——按序逐个处理。
for fn in ["唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt", "全宋词.txt"]:
    # os.path.join 拼路径：自动补分隔符，跨平台的 sprintf("%s/%s")，更稳。
    p = os.path.join(KB, fn)
    # 文件存在才统计：缺语料不致命，跳过即可——数据工程的容错习惯。
    if os.path.exists(p):
        # Counter.update 吃可迭代对象并逐元素计数+1；括号里是"生成器表达式"：
        # 边遍历整篇文本边过滤汉字（惰性求值，不先建完整数组，省内存）。
        freq.update(c for c in open(p, encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")

# ---------- 解析范诗 ----------
# 把长字符串按空白切成姓名数组再转 set（哈希集合）：集合判"是否名家"是 O(1)，
# 比遍历数组快得多；名单里"韦应物"重复出现，set 自动去重。
FAMOUS = set("李白 杜甫 王维 孟浩然 白居易 李商隐 杜牧 刘禹锡 柳宗元 韦应物 岑参 高适 王昌龄 王之涣 贾岛 姚合 钱起 刘长卿 卢纶 韩翃 司空曙 韩愈 孟郊 张籍 王建 元稹 温庭筠 韦庄 杜荀鹤 许浑 罗隐 陆龟蒙 皮日休 崔颢 祖咏 常建 刘方平 张祜 朱庆馀 郑谷 韦应物 戴叔伦 皇甫冉 郎士元 畅当 裴迪 王翰 王湾 张九龄".split())

# 定义"解析一个语料文件"的函数：fn=文件名，source=来源标记（本脚本未用到，
# 历史遗留参数，保留不影响逻辑）。
def parse_file(fn, source):
    # 空列表（动态数组）：攒解析结果用。
    out = []
    # 一次性把整份语料读成一个大字符串（≈malloc 文件大小+fread 全量），
    # 几 MB 的文本量这样做完全可行。
    text = open(os.path.join(KB, fn), encoding="utf-8").read()
    # 按"空行"（连续两个 \n）把全文切成一首一块的记录数组，逐首处理。
    for rec in text.split("\n\n"):
        # 大正则解析记录头：【书名】《题目》（作者[·别名]）换行+正文；
        # (?:...)? 是可选非捕获组（兼容"作者·字"结构）、+? 是非贪婪匹配（遇到第一个》就停）、
        # re.S 让 . 也匹配换行（正文跨行）。不匹配返回 None 即跳过——脏数据直接淘汰。
        m = re.match(r"【[^】]+】《(.+?)》（(?:([^·）]*)·)?([^）]*)）\n(.+)", rec.strip(), re.S)
        # 格式不符的记录丢弃：宁缺毋滥的数据清洗原则。
        if not m:
            continue
        # 元组解包：4 个捕获组一次性赋给 4 个变量；"_"是约定的"丢弃位"（这里不要别名组）。
        # ≈ C 里把 sscanf 的多个出参一次收齐，但写法简洁得多。
        title, _, author, body = m.groups()
        # 往结果数组追加三元组 (题目, 作者, 正文)；strip() 去掉首尾空白（含换行）。
        out.append((title, author, body.strip()))
    # 返回整个列表——Python 函数可直接返回复合结构，无需出参指针。
    return out

# 解析两份语料并用 + 拼接两个列表（动态数组 concat）：
# 得到"唐诗三百首 + 千家诗"的全部诗，作为第一优先诗池。
poems_all = parse_file("唐诗三百首.txt", "ts") + parse_file("千家诗.txt", "qjs")

# 全唐诗按名作家抽样
# 一行建两个变量（右侧是元组，多重赋值）：seen_body=已见正文的 MD5 指纹集合（去重），
# tang=名家诗列表——一个管"查重"、一个管"收藏"。
seen_body, tang = set(), []
# 链式：读全唐诗→按空行切→逐首迭代（open().read().split() 从里向外层层返回）。
for rec in open(os.path.join(KB, "全唐诗.txt"), encoding="utf-8").read().split("\n\n"):
    # 匹配全唐诗固定格式：【全唐诗】《题》（作者）\n正文；re.S 支持跨行正文。
    m = re.match(r"【全唐诗】《(.+?)》（(.+?)）\n(.+)", rec.strip(), re.S)
    # 不合格式跳过。
    if not m:
        continue
    # 解包三个捕获组：题目、作者、正文。
    title, author, body = m.groups()
    # in 对 set 是哈希查找 O(1)：作者不在名家名单里的直接丢弃——
    # 全唐诗近五万首，只取最经典作者以控数量保质量。
    if author not in FAMOUS:
        continue
    # 对正文算 MD5 指纹：encode() 把字符串按 UTF-8 转成 bytes（显式区分"字符"与"字节"，
    # Python3 的 str≈wchar 串，bytes≈char 串），hexdigest() 得 32 位十六进制串。
    # 内容相同的诗指纹相同——跨书重收全靠它识别。
    h = hashlib.md5(body.encode()).hexdigest()
    # 指纹已在集合中=重复诗，丢弃（in 对 set 为哈希查询）。
    if h in seen_body:
        continue
    # 首次见到：登记指纹。
    seen_body.add(h)
    # 收入名家诗列表（三元组入动态数组）。
    tang.append((title, author, body.strip()))
# 原地洗牌（Fisher-Yates）：打乱名家诗顺序，让后续按序取样时各作家分布均匀。
random.shuffle(tang)

# 定义体裁判别函数：输入正文，返回 (体裁名, 句子列表) 二元组，不合格返回 None。
# 这是"真诗为骨"的准入闸门：只有标准近体诗才配进入训练数据。
def classify(body):
    # 函数文档字符串（三引号）：说明返回形态，存入该函数的 __doc__。
    """返回 (体裁名, [句]) 或 None。"""
    # 推导式+re.split：按，。？！把正文切成"句"数组，并过滤掉切出来的空串
    # （if u.strip()）——这是全管线最基本的"断句"操作。
    units = [u.strip() for u in re.split(r"[，。？！]", body) if u.strip()]
    # 一行三重体检（and 短路求值，同 C 的 &&）：①句数是 4（绝句）或 8（律诗），
    # in 判断元组成员；②units 非空；③把每句字数收集成 set，集合长度为 1
    # ⇒每句字数全相等——杂言/长短句（如词）在此被淘汰。
    if len(units) in (4, 8) and units and len(set(len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units)) == 1:
        # 取第一句的纯汉字数（5 或 7），用来定"五言/七言"。
        n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
        # 字数必须是 5/7 言，且 all(re.fullmatch(...)) 要求每句"从头到尾"都是纯汉字
        # （fullmatch=整串匹配，含英文或杂符即淘汰）——双保险的规格校验。
        if n in (5, 7) and all(re.fullmatch(r"[\u4e00-\u9fff]+", u) for u in units):
            # 嵌套三元表达式（C 的 a?b:c 套娃）：先按句数定绝/律，再按字数定五/七，
            # 拼出体裁名——一行顶四行 if。
            g = ("五言绝句" if n == 5 else "七言绝句") if len(units) == 4 else ("五言律诗" if n == 5 else "七言律诗")
            # 返回 (体裁名, 句子列表) 二元组——C 里得靠结构体或出参，这里直接打包。
            return g, units
    # 所有规格都不合：返回 None（≈NULL），调用方据此跳过。
    return None

# 定义"在一联诗里找意象"的函数——imagery.py 意象词典的查询入口。
def find_imagery(line):
    # 把字典 items()（键值对数组）按键长度"倒序"排序后解包遍历：
    # key=lambda x: -len(x[0]) ——lambda 即内联匿名函数，取负号实现降序；
    # 长词优先保证"河汉"先于"河"命中，避免短词抢走匹配。
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        # 子串包含判断（C 得手写 strstr）：意象词出现在诗句里即命中。
        if w in line:
            # 三元表达式做类型兼容：值是列表就直接用；是单个字符串（如"茶"那条特例）
            # 就包成长度 1 的列表——统一后续接口，防御数据类型不齐。
            opts = imps if isinstance(imps, list) else [imps]
            # 返回 (意象, 随机抽的意蕴)：random.choice 从数组等概率取一个元素。
            return w, random.choice(opts)
    # 整句一个意象都没命中：返回双 None，调用方走"无意象解释"分支。
    return None, None

# 题目关键字 -> 立意用词 的映射表（哈希表）：把题目里的字翻译成通顺的题材词
# （如"送"→"送别"），让生成的立意句读起来自然。
KEY2WORD = {"送": "送别", "别": "离别", "思": "思念", "怀": "怀远", "咏": "咏物",
            # 映射表续行（在花括号内部，注释合法）：边塞/归乡/读书/夜坐。
            "边": "边塞", "塞": "边塞", "归": "归乡", "书": "读书", "夜": "夜坐",
            # 映射表续行：村田四季——收尾完成这张 16 键小表。
            "村": "田家", "田": "田家", "春": "春景", "秋": "秋景", "冬": "冬日", "夏": "夏日",
            # v1.5 续增：侠/剑/酒 三键（配合 EMO_BY_KEY 新增原型），立意读起来更顺。
            "侠": "侠气", "剑": "剑气", "酒": "酒意"}

# 定义"生成立意句"函数：输入题目，输出如"借送别之景，写离情…"的一句话。
def make_liyi(title):
    # next()+生成器表达式：在题目里找"第一个出现在 EMO_BY_KEY 的关键字"，
    # 第二参数 None 是找不到时的默认值——等价 C 里 for 循环+found 标志+break 的合成体。
    key = next((k for k in EMO_BY_KEY if k in title), None)
    # 查情感方向：get 带默认值 EMO_DEFAULT——key 为 None 或缺键都兜底，
    # 保证立意句永不残缺（防脏数据的习惯性写法）。
    # v1.5 兼容：EMO_BY_KEY 值已改为列表（一键多原型），random.choice 随机抽一条；
    # 仍是字符串的旧数据也能走通（isinstance 双保险）。
    pool = EMO_BY_KEY.get(key, EMO_DEFAULT)
    emo = random.choice(pool) if isinstance(pool, list) else pool
    # 查立意关键词；fallback 用切片 title[:2]：取题目前两字（[:2] 即下标 0、1，
    # Python 切片越界安全，短题目也不会崩）。
    kw = KEY2WORD.get(key, title[:2])
    # 随机挑一条立意模板并按关键字参数填空：format(kw=..., emo=...) 对应模板里的
    # {kw}{emo} 占位符——sprintf 的命名参数版。
    return random.choice(LIYI_PLAIN).format(kw=kw, emo=emo)

# 无意象时的解释模板池：只谈章法角色/笔致、不硬凑意象——保证任何句子都有得解释，
# 不会因为"查无意象"而生成空话或报错。
NOIMG_PATTERNS = [
    # 模板1：以角色点评+写景赞语收尾，情在言外。
    "\"{line}\"——{role}，写景如画，情在言外。",
    # 模板2：用笔致形容词评句，"不假雕饰"是传统评点语。
    "\"{line}\"——句意{adj}，不假雕饰而韵味自出。",
    # 模板3：平平道来自有深致——朴实风格的兜底评语。
    "\"{line}\"——此句{role}，平平道来，自有深致。",
]
# 模板池收尾。

# 模块级去重集合（下划线开头="模块私有"约定，≈static 局部化）：
# 登记已生成过的解释句，防止几千条样本里解释文案大量重复。
_used = set()
# 定义"单句解释"函数：给一句诗+它的章法角色，产出一条不重复的解释句。
def explain_unit(u, role):
    # range(6) 生成 0..5 序列，循环最多 6 次；"_"表示不需要循环变量的占位名；
    # 思路=重试 6 次抽一条"没用过"的解释。
    for _ in range(6):
        # 解包查询结果：命中得 (意象, 意蕴)，未命中得 (None, None)。
        img, imp = find_imagery(u)
        # is None 判空（≈p==NULL）：这句诗里没找到意象。
        if img is None:
            # 无意象分支：选"无意象模板"，填诗句/章法角色/随机笔致形容词——
            # 每个占位符都有值，解释不会残缺。
            s = random.choice(NOIMG_PATTERNS).format(line=u, role=role, adj=random.choice(ADJ))
        # 有意象分支。
        else:
            # 意象模板池里随机选一条，一次性填入全部占位符（跨两行的括号内续行）；
            # imp2=imp 是"别名占位"——两套模板占位符名字不同，同值双传以兼容。
            s = random.choice(LINE_PATTERNS).format(
                line=u, img=img, imp=imp, imp2=imp, role=role, adj=random.choice(ADJ))
        # 集合查重 O(1)：这条解释没用过才收。
        if s not in _used:
            # 登记进去重集合。
            _used.add(s)
            # 返回成品解释。
            return s
    # 重试 6 次仍全撞重（概率极低）：返回最后一条兜底，保证函数必有返回值。
    return s

# 定义"整首诗解释"函数：把逐句解释用换行缝成多行段落。
def make_explanation(units):
    # 4 句=绝句分支。
    if len(units) == 4:
        # join 把字符串数组用 \n 缝成一段（先算总长的一次性拼接，优于循环 strcat）；
        # enumerate(数组) 同时给下标 i 和元素 u（C 里 for(i=0;…) 的合体写法）；
        # 每句按位配"起承转合"角色再逐句解释——章法感就来自这里。
        return "\n".join(explain_unit(u, ROLE_JUE[i]) for i, u in enumerate(units))
    # 律诗分支：两句拼"一联"（units[i*2]+"，"+units[i*2+1]+"。"）作为解释对象，
    # 按 0..3 联序配 ROLE_LV 的四联角色——括号内续行的推导式，i*2 是联首下标。
    return "\n".join(
        explain_unit(units[i * 2] + "，" + units[i * 2 + 1] + "。", ROLE_LV[i])
        for i in range(4))

# 作诗样本总仓（动态数组）：所有组装完成的 SFT 样本先攒在这里。
samples = []
# 定义"装一条作诗样本"的函数：输入题目/作者/断好的句子/体裁，产出一条 SFT 字典。
def add_poem(title, author, units, genre):
    # 随机指令模板填题目与体裁 → 样本的 instruction 字段（模型看到的"问"）。
    instr = random.choice(INSTR_TPL).format(t=title, g=genre)
    # 把断句数组还原成"一联一行"的诗体排版（本行最密集）：range(0, len, 2) 步长 2
    # 取每联首句下标 i；i 是偶位句→后接"，"再拼下句加"。"——嵌套三元+生成器表达式
    # 一气呵成，等价 C 里双重 for 循环拼 sprintf 缓冲区。
    body = "\n".join(units[i] + ("，" if i % 2 == 0 else "。") + (units[i + 1] + "。" if i % 2 == 0 else "") for i in range(0, len(units), 2))
    # f-string 大拼接：把"立意→诗→意象解释"按固定骨架组装成 output 字段——
    # 模型将学会照此纪律作答（先立意、次成诗、末逐句解意象），这就是"格式锚定"。
    output = f"立意：{make_liyi(title)}\n\n诗：\n《{title}》\n{body}\n\n意象解释：\n{make_explanation(units)}"
    # 追加一条字典（哈希表/类 JSON 对象）：instruction/input/output 是 SFT 三件套，
    # input 留空（无上下文的单轮样本）；_src 是溯源标记（人看的元数据，写出前会删）。
    samples.append({"instruction": instr, "input": "", "output": output, "_src": f"{author}"})

# 各体裁已收数量的计数器（Counter：新键默认从 0 起，不怕"未初始化"）。
count_by_genre = Counter()
# 体裁配额表（哈希表）：四体裁各收多少条——数据配比是数据工程的"配方"，
# 防止某一体裁一家独大导致模型偏科。
PLAN = {"五言绝句": 500, "七言绝句": 500, "五言律诗": 450, "七言律诗": 450}
# 定义"投喂一个诗池"的函数：遍历诗池，按配额与质检规则收割合格样本。
def feed(pool):
    # 解包遍历 (题目, 作者, 正文) 三元组数组——for-in 直接走元素，无需下标。
    for title, author, body in pool:
        # all(... for g, v in PLAN.items())：items() 把字典变成 (键,值) 对数组并解包；
        # 全部体裁都收满 → return 提前收工（同 C 的 return，函数即出）。
        if all(count_by_genre[g] >= v for g, v in PLAN.items()):
            return
        # 判体裁：不合规格得 None。
        cls = classify(body)
        # not cls：判空失败即跳过——闸门之一（体裁规格）。
        if not cls:
            continue
        # 解包体裁名与句子数组。
        g, units = cls
        # 闸门之二：该体裁已超额（配额控制）或韵脚不齐（平水韵校验）都不要——
        # or 短路求值，先查便宜的配额再查韵表。
        if count_by_genre[g] >= PLAN[g] or not rhyme_ok(units):
            continue
        # 闸门之三：题目自带"绝句/律诗/五言"等体裁字样的跳过——否则会出现
        # 指令说"作七言绝句"而题目又叫"X言绝句"的自相矛盾样本。
        # re.search 是全文找（不像 match 只锚行首），| 是正则的"或"。
        if re.search(r"[五六七]言|绝句|律诗|排律|长句|杂言", title):
            continue  # 题目自带体裁字样，避免与指令矛盾
        # 三道闸都过：该体裁计数 +1（Counter 对新键自动从 0 起算）。
        count_by_genre[g] += 1
        # 组装并入库一条样本。
        add_poem(title, author, units, g)

# 先喂"三百首+千家诗"诗池——最经典的语料优先入池。
feed(poems_all)
# 再喂名家全唐诗池补量——上一池没收满的体裁到这里凑数（feed 内部有配额闸）。
feed(tang)
# 打印作诗样本统计：sum(...) 对计数器的值求和得总数，dict() 把 Counter 转普通字典
# 便于打印——数据工程的进度日志习惯。
print("作诗样本:", sum(count_by_genre.values()), dict(count_by_genre))

# ---------- 韵部问答（扩至 240） ----------
# 推导式筛"可出题的韵字"：遍历 freq 字典默认遍历键；条件=单字、在韵表里有韵部、
# 语料频次≥200——生僻字不配出题，出题字必须是常见字。
yun_words = [w for w in freq if len(w) == 1 and char2rhyme.get(w) and freq[w] >= 200]
# 洗牌：出题用字随机化，避免题目按字表顺序扎堆。
random.shuffle(yun_words)
# 韵部问答样本仓（空动态数组）。
yun_qa = []
# 遍历候选字，逐个攒题。
for w in yun_words:
    # 攒够 270 条提前 break（同 C）——上限比标题 240 略高，给后续质检剔除留余量。
    if len(yun_qa) >= 270:
        break
    # 该字的全部韵部名排序（一字可属多韵部，这里取字典序第一作标准答案）。
    names = sorted(char2rhyme[w])
    # [0] 取首元素：钦定的"本字韵部"。
    name = names[0]
    # 推导式找"同部常用字"：遍历整个 char2rhyme 的键，条件=不是本字、也属该韵部、
    # 语料频次≥30——凑一桌够格的"同部韵字"做答案素材。
    same = [c for c in char2rhyme if c != w and name in char2rhyme[c] and freq.get(c, 0) >= 30]
    # 按频次倒序排（key 取 -freq 实现降序；freq.get(c,0) 缺键给 0 防崩）——
    # 越常用的字排越前，答案质量越高。
    same.sort(key=lambda c: -freq.get(c, 0))
    # 同部常用字不足 8 个的题没意思，跳过——题目质量的数量门槛。
    if len(same) < 8:
        continue
    # 切片 [:16] 取前 16 个（越界安全），顿号 join 成一串做标准答案展示。
    show = "、".join(same[:16])
    # 从 3 种问法随机选一种做 instruction（f-string 现场嵌字）——
    # 问法多样让模型不背死单一模板；列表字面量内的注释行合法。
    qi = random.choice([
        # 问法1：直问韵部归属+同部字。
        f"「{w}」字在平水韵中属哪个韵部？同部还有哪些常用字？",
        # 问法2：从"作诗押韵"场景切入，更贴近实战。
        f"作近体诗时用「{w}」作韵脚，其余韵脚应用什么字？",
        # 问法3：换"押哪一部"的说法再问一遍。
        f"「{w}」押平水韵哪一部？请列举同部常用字。",
    ])
    # 标准答案 output（括号续行的两个 f-string 隐式拼接成一段）：先报韵部与同部字，
    # 再补押韵纪律——"首句可借邻韵、其余不可出韵"正是近体诗的用韵规则，
    # 把领域知识直接写进训练目标。
    ao = (f"「{w}」属平水韵【{name}】部。同部常用韵字有：{show}等。"
          f"作近体诗时，韵脚须与此部字相押（首句可借邻韵），不可出韵。")
    # 装样本入库，_src 标"韵表生成"便于溯源统计。
    yun_qa.append({"instruction": qi, "input": "", "output": ao, "_src": "韵表生成"})
# 打印韵部问答的产出数量。
print("韵部问答:", len(yun_qa))

# ---------- 名句出处问答（300） ----------
# 再解析三份语料合一个"出处题"池：唐诗三百首+宋词三百首+千家诗
# （宋词在此加入——出处题不限近体诗，词也考）。
src_pool = parse_file("唐诗三百首.txt", "ts") + parse_file("宋词三百首.txt", "sc") + parse_file("千家诗.txt", "qj")
# 洗牌：出处题的抽样顺序随机化。
random.shuffle(src_pool)
# 出处问答样本仓。
src_qa = []
# 遍历诗池攒题。
for title, author, body in src_pool:
    # 攒够 400 条收工。
    if len(src_qa) >= 400:
        break
    # 取第一个句号前的文字当"名句"：split("。")[0] 即首段，strip 去空白——
    # 名句问答用整句开头最自然。
    first = body.split("。")[0].strip()
    # 名句长度闸：短于 6 字没辨识度、长于 40 字太难背，都跳过。
    if len(first) < 6 or len(first) > 40:
        continue
    # 判断是不是"词"：①作者字段带"词"字；或 ②首句前半段（逗号前）纯汉字数
    # 不是 5/7——近体诗必是整齐的五/七言，长短不齐即词的特征（词又称长短句）。
    is_ci = "词" in author or len(re.sub(r"[^\u4e00-\u9fff]", "", first.split("，")[0])) not in (5, 7)
    # 三元表达式按词/诗选问法用词。
    kind = "哪首词" if is_ci else "哪首诗"
    # 装样本：instruction=名句出处问；output=作者+题目+全文（f-string 拼接）。
    # 字典字面量跨多行，内部注释合法。
    src_qa.append({
        # 键 instruction：把名句嵌进问句。
        "instruction": f"「{first}」出自{kind}？",
        # 键 input：单轮样本固定留空。
        "input": "",
        # 键 output：完整出处+原文，训练"忆诗定位"能力。
        "output": f"出自{author}的《{title}》：\n{body}",
        # 键 _src：溯源标记。
        "_src": "出处生成"})
# 打印出处问答数量。
print("出处问答:", len(src_qa))

# ---------- 体裁辨识（250） ----------
# 体裁辨识样本仓。
meter_qa = []
# 混合题池：三百首+千家诗全量 + 名家诗前 400（切片 [:400]，越界安全）——
# 多源混合让考题的文本风格更杂，防模型只认某本书的排版。
pool2 = poems_all + tang[:400]
# 洗牌。
random.shuffle(pool2)
# 遍历题池。
for title, author, body in pool2:
    # 攒够 480 条收工（同样给质检剔除留余量）。
    if len(meter_qa) >= 480:
        break
    # 判体裁，不合格跳过。
    cls = classify(body)
    if not cls:
        continue
    # 解包体裁名与句子数组。
    g, units = cls
    # 取首句纯汉字数（5 或 7）——本题的"标准答案"之一。
    n = len(re.sub(r"[^\u4e00-\u9fff]", "", units[0]))
    # 字符串 + 拼接（≈strcat）取前两句拼成"考题节选"。
    excerpt = units[0] + "，" + units[1] + "。"
    # 两种问法随机选一（列表内注释合法）。
    qi = random.choice([
        # 问法1：口语化问五言还是七言。
        f"「{excerpt}」每句几个字？是五言还是七言？",
        # 问法2："判断体裁字数"的书面问法。
        f"判断下面诗句的体裁字数：「{excerpt}」",
    ])
    # 标准答案：每句几字、五言/七言（嵌三元）、全诗体裁与句数，末尾附纪律句
    # "每句必须恰 n 字"——把格律硬约束教进答案文本里。
    ao = f"每句{n}字，是{'五言' if n == 5 else '七言'}；全诗为{g}（共{len(units)}句）。作此体裁时每句必须恰{n}字。"
    # 装样本入库。
    meter_qa.append({"instruction": qi, "input": "", "output": ao, "_src": "体裁辨识"})
# 打印体裁辨识数量。
print("体裁辨识:", len(meter_qa))

# ---------- 合并金标准 + 典故/身份 ----------
# 读入手写金标准样本：json.load 把 JSON 文本反序列化成 Python 对象（字典数组）——
# 人工精标的"教科书样本"质量最高，排序上也放最前。
gold = json.load(open(os.path.join(TD, "poems_pilot.json"), encoding="utf-8"))
# 同上，读问答类金标准。
qa = json.load(open(os.path.join(TD, "qa_pilot.json"), encoding="utf-8"))
# 两列表拼接后遍历（+ 生成新列表，不改原表）。
for d in gold + qa:
    # d 是字典，直接赋新键即插入（哈希表写操作）：打上"手写金标准"溯源标记。
    d["_src"] = "手写金标准"

# 手写"身份认知"样本列表：教模型"我是谁、会什么、行为纪律是什么"——
# SFT 里的人格锚定（每条都是标准三件套字典）。
ident_extra = [
    # 身份样本1：自报家门+能力清单+作诗纪律（平水韵/先立意/逐联解意象）。
    {"instruction": "请介绍一下你自己", "input": "", "output": "我是 poemly，主人的诗词创作助手。我能作五言七言、绝句律诗，用韵必依平水韵，先立意后成篇，写完逐联解意象；也能查典故出处、检索范作、讲论词话诗话。"},
    # 身份样本2：会写词——依词林正韵、按词牌句读填，并指定可点词牌。
    {"instruction": "你会写词吗？", "input": "", "output": "会。词依词林正韵，按词牌句读填词。若你指定词牌（如《浣溪沙》《鹧鸪天》），我按其格律填写，并说明所押词韵。"},
    # 身份样本3：解释"为何先立意"——把行为习惯写进自我认知，防止模型漂移。
    {"instruction": "作诗前你为什么总要先说立意？", "input": "", "output": "先立意是我的本分：动笔前确定主题与情感方向，围绕立意选意象、安排章法，诗才能情景交融、脉络贯通。这不需你操心，我自会如此作答。"},
    # 身份样本4：知识库清单——声明可查韵书/总集/诗话，"不作无据之谈"是反幻觉约束。
    {"instruction": "你的知识库能查到什么？", "input": "", "output": "我备有平水韵、词林正韵字表，全唐诗、全宋词及唐诗宋词三百首、千家诗，诗经、楚辞，声律启蒙、笠翁对韵、幼学琼林、龙文鞭影，人间词话、沧浪诗话。查韵部、找范作、核典故出处都可依赖实据，不作无据之谈。"},
]
# 给身份样本逐条打溯源标记（字典赋新键）。
for d in ident_extra:
    d["_src"] = "手写金标准"

# 七路数据大合并（列表 concat 链）：金标准→身份→作诗→韵部→出处→体裁；
# 金标准排最前——训练样本顺序也影响学习效果，人写的放前面当"开蒙教材"。
data = gold + qa + ident_extra + samples + yun_qa + src_qa + meter_qa
# 打印合并总数。
print("合并总数:", len(data))

# ---------- 全量质检 ----------
# 质检问题清单：每条错误是"[下标]描述"字符串，攒齐后统一剔除。
errors = []
# enumerate 带下标遍历：i 是样本在总表里的编号（报错定位要靠它）。
for i, d in enumerate(data):
    # 取该样本的标准答案字段。
    out = d["output"]
    # 子串判断识别"作诗类"样本（output 里有"诗：\n《"开头）——只对这类做格律质检。
    if "诗：\n《" in out:
        # re.search 全文抠出题目和正文（re.S 跨行），两个捕获组。
        m2 = re.search(r"诗：\n《(.+?)》\n(.+)", out, re.S)
        # 解包题目与正文。
        title, body = m2.groups()
        # 把 output 里的诗再独立断句一遍（截到"意象解释"节之前）——
        # 复检不信任组装时的中间数据，独立重算才是真质检。
        units = [u for u in re.split(r"[，。？！]", body.split("\n\n意象解释")[0]) if u.strip()]
        # 每句纯汉字长度数组（推导式逐句剥除非汉字再 len）。
        lens = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units]
        # 体检①：句长集合长度≠1（各句不齐）或首句不是 5/7 字——记错误（f-string 拼错误信息）。
        if len(set(lens)) != 1 or lens[0] not in (5, 7):
            errors.append(f"[{i}]{title}句长{lens}")
        # 体检②：句数不是 4（绝）或 8（律）——记错误。
        elif len(units) not in (4, 8):
            errors.append(f"[{i}]{title}句数{len(units)}")
        # 体检③：押韵不合格——把全部韵脚字拼进错误信息方便人工排查：
        # units[1::2] 取偶数句，[-1] 取每句末字，join 缝成串。
        elif not rhyme_ok(units):
            feet = "".join(re.sub(r"[^\u4e00-\u9fff]", "", u)[-1] for u in units[1::2])
            errors.append(f"[{i}]{title}韵脚{feet}")
        # 体检④：找 output 最后一个非空行（splitlines 按行切、推导式滤空、[-1] 取末行）。
        last = [l for l in out.splitlines() if l.strip()][-1]
        # 末行以"以上/总之/希望/如有"开头=客套收尾——记错误：
        # LLM 的"以上便是…"式尾巴必须扼杀在数据里，否则模型学会油腔滑调。
        if re.match(r"^(以上|总之|希望|如有)", last.strip()):
            errors.append(f"[{i}]{title}客套收尾")
    # 体检⑤：全文任意位置出现客套语也记错（与前一条双保险）。
    if "以上便是" in out or "希望你喜欢" in out:
        errors.append(f"[{i}]客套语")

# 从错误串反解坏样本下标集合：e.split("]")[0] 取"]"前段（如"[12"），[1:] 去掉"["，
# int 转整数——字符串再解析的凑合写法但够用；set 去重并供 O(1) 判"在不在黑名单"。
bad = set(int(e.split("]")[0][1:]) for e in errors)
# 列表推导式重建数据：下标不在黑名单的才保留——宁可少收，不让坏样本污染训练。
data = [d for i, d in enumerate(data) if i not in bad]
# 打印剔除数与最终数。
print("质检剔除:", len(bad), "条；最终:", len(data), "条")

# 收尾清洗：遍历全部幸存样本。
for d in data:
    # pop("_src", None) 删除溯源字段（第二参数是缺键时的默认值，防 KeyError）——
    # _src 是给人看的元数据，SFT 训练用不到，进交付物前剥掉。
    d.pop("_src", None)
# 全量写出 JSON 数据集：ensure_ascii=False 让中文原样存储（否则变 \uXXXX 转义），
# indent=1 缩进一级便于人工抽查；"w" 写模式 + UTF-8——数据交付物诞生。
json.dump(data, open(os.path.join(TD, "poemly_sft_v1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 完工日志。
print("已写出 poemly_sft_v1.json")
