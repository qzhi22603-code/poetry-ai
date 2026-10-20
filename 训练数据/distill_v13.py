# -*- coding: utf-8 -*-
"""v1.3 蒸馏（干净版）：deepseek 命题原创诗 → 三重质检 → originals_v13.jsonl"""
import json, os, re, time, random, urllib.request, threading
from concurrent.futures import ThreadPoolExecutor
from opencc import OpenCC

cc = OpenCC("t2s")
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"
OUT = os.path.join(TD, "originals_v13.jsonl")
random.seed(5)

_cfg = json.load(open(r"C:\Users\38107\.zcode\v2\provider_config.json", encoding="utf-8"))
TOKEN = [r for r in _cfg["config"]["providerConfigRules"]["providerRules"] if r["providerId"] == "bupt-llm-gw"][0]["config"]["access"]["apiKey"]

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

CORPUS = set()
for fn in ["全唐诗.txt", "唐诗三百首.txt", "千家诗.txt", "宋词三百首.txt", "全宋词.txt"]:
    for rec in open(os.path.join(KB, fn), encoding="utf-8").read().split("\n\n"):
        for ln in rec.splitlines()[1:]:
            for s in re.split(r"[，。？！]", ln):
                s = re.sub(r"[^\u4e00-\u9fff]", "", s).strip()
                if len(s) >= 4:
                    CORPUS.add(s)

def validate(units, genre_n, genre_len):
    if len(units) != genre_n:
        return "句数"
    if any(len(u) != genre_len for u in units):
        return "字数"
    feet = [u[-1] for u in units[1::2]]
    parts = [char2rhyme.get(f) for f in feet]
    if not all(parts) or not set.intersection(*parts):
        return "韵部"
    if any(u in CORPUS for u in units):
        return "撞句"
    return None

THINGS = ["荷花", "梅花", "菊花", "兰花", "竹", "松", "雁", "燕", "蝉", "鹤", "明月", "雪", "春风", "秋雨", "霜", "露", "江河", "湖海", "青山", "溪流", "小桥", "孤舟", "钟声", "渔火", "明镜", "宝剑", "茶", "酒", "柳絮", "枫叶", "梧桐", "芭蕉", "杜鹃", "鹧鸪", "萤火", "瀑布", "长城", "黄河", "长江", "西湖", "洞庭湖", "庐山", "泰山", "大漠", "草原", "边关", "渡口", "书斋", "古寺", "高阁", "油灯", "笛声", "砧声", "白鹭", "鸥鸟", "春蚕", "蜜蜂", "蝴蝶", "古琴", "棋", "书信", "行囊", "白发", "梦"]
SCENES = ["春晓", "夏夜", "秋暮", "冬晨", "送别", "思乡", "边塞", "田园", "羁旅", "重阳登高", "七夕", "中秋", "元宵", "清明", "白露", "冬至", "除夕", "宴饮", "夜读", "晓行", "泛舟", "登楼", "听雨", "赏雪", "怀古", "访友", "归隐", "闺中", "宫怨", "少年游"]
GENRES = [("七言绝句", 4, 7), ("五言绝句", 4, 5), ("七言律诗", 8, 7), ("五言律诗", 8, 5)]

titles = [f"咏{t}" for t in THINGS] + SCENES
jobs = [(titles[i], *GENRES[i % 4]) for i in range(len(titles))]
for t in random.sample(titles, min(90, len(titles))):
    g = random.choice(GENRES)
    jobs.append((t, g[0], g[1], g[2]))
print("任务数:", len(jobs), flush=True)

done_titles = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        try:
            d = json.loads(line)
            done_titles.add((d["t"], d["g"]))
        except Exception:
            pass
print("已完成:", len(done_titles), flush=True)

lock = threading.Lock()
stats = {"ok": 0, "fail": 0}

def gen(job):
    try:
        title, g, n, ln = job
        if (title, g) in done_titles:
            return
        for attempt in range(3):
            try:
                req = urllib.request.Request("https://myai.bupt.edu.cn/llm-gw/v1/chat/completions",
                    data=json.dumps({"model": "deepseek-v4-flash", "max_tokens": 900, "temperature": 0.9, "messages": [
                        {"role": "user", "content": f"以《{title}》为题作一首{g}（每句{ln}字，共{n}句）。只输出诗句本身，不要任何解释。"}]}).encode(),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    resp = json.load(r)
                msg = resp.get("choices", [{}])[0].get("message", {})
                text = msg.get("content") or msg.get("reasoning_content") or ""
                if not text.strip():
                    time.sleep(2)
                    continue
            except Exception:
                time.sleep(3)
                continue
            units = [re.sub(r"[^\u4e00-\u9fff]", "", u) for u in re.split(r"[，。？！\n]", text)]
            units = [u for u in units if u]
            if validate(units, n, ln) is None:
                with lock:
                    with open(OUT, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"t": title, "g": g, "u": units}, ensure_ascii=False) + "\n")
                    stats["ok"] += 1
                    done_titles.add((title, g))
                return
        with lock:
            stats["fail"] += 1
    except Exception:
        pass

with ThreadPoolExecutor(max_workers=1) as ex:
    list(ex.map(gen, jobs))
print("生成完毕: 成功", stats["ok"], "失败", stats["fail"], flush=True)
