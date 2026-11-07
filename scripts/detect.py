#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单篇/单目录 AI 味检测报告（去AI味 v2 的第一步，只检测不改写）。

用法：
    python3 scripts/detect.py <文件或目录> [--json] [--max-hits 5]
    python3 scripts/detect.py <文件> --candidates [--out 候选.json]

--candidates 抽取语义层候选（同义重命名段 / 段间衔接接口 / 冒号句 / 三连同构），
交给会话内 Claude 按 references/semantic-criteria.md 判断，结果并入报告。

分级：
    A 机械改    固定句式/标点问题，模型复核后给建议，用户回复后改
    B 建议改    需要句式重组或换说法，模型逐条复核后给建议，用户回复后改
    C 只报告    结构/节奏类分布特征，默认不改
    F 指纹      分模型特征（破折号/分号/引号），解读必须带方向

人类参考值来自两轮实测（见 RESEARCH.md）：
- 第一轮 629 篇对照（5 模型各 60 篇 vs 329 篇人类，不配对）
- 第二轮 270 对同题同事实配对 + 43 万次语义判断
标 [可调] 的阈值是经验值，换语料后应重新标定。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Windows 下输出被重定向或接管道时默认用 GBK，遇到特殊符号会报错；统一用 UTF-8 输出
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

EXTS = {".md", ".txt"}

# ---------------- 正则指标（level, 名称, 模式, 人类参考/千字, 建议） ----------------

REGEX_HITS = [
    ("A", "翻案腔",
     r"(?:不是|并非|不在于|与其说)[^，。！？\n]{1,20}[，]?(?:而是|而在于|不如说)",
     "0.22", "正面直陈：删「不是A」，直接给B。见规则1"),
    ("A", "提示语冒号",
     r"(?:一句话(?:总结|说|概括)|简单说|说白了|总结|小结|结论|核心(?:是|在于|观点)?"
     r"|关键(?:是|在于)?|重点(?:是)?|原因(?:如下|有|在于)?|问题(?:是|在于)?"
     r"|答案(?:是)?|本质(?:是|上)?|具体(?:来说|如下|包括)?"
     r"|举例(?:来说)?|换句话说|也就是说|我的(?:观点|判断|结论)|建议(?:是)?)[：:]",
     "0.08", "删提示语直接写内容；前半句承接上文时只换标点。见规则2"),
    ("A", "起手式",
     r"(?:说白了|说穿了|先说结论)[，,]",
     "0.008", "删掉直接给判断。见规则3"),
    ("A", "当…时从句",
     r"当[^，。\n]{2,20}(?<!的时候)时，",
     "—", "删「当」和「时」，让从句直接作前一分句。见规则4"),
    ("A", "前置话题壳",
     r"(?:对于[^，。\n]{2,15}来说|对[^，。\n]{2,15}而言|就[^，。\n]{2,15}而言|在[^，。\n]{2,12}方面)",
     "—", "对象直接放到主语位，删壳子。见规则4"),
    ("A", "句首连接词",
     r"(?:^|\n)\s{0,3}(?:然而|因此|此外|与此同时|换言之|总而言之)[，、]",
     "—", "移到主语后，或换「不过」「其实」。见规则4"),
    ("B", "顿号并列≥3",
     r"[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}",
     "1.78", "能概括就概括；必须保留时打破其中一项的句法。见规则5"),
    ("B", "过长前置定语",
     r"(?:一个|一种|一套|这种|这个)[^，。、；：！？\n]{15,}的[一-鿿]{2,5}",
     "≈0.1", "拆成两个分句，「的」字连续两个以上同。见规则4"),
    ("H", "拟人化喻体",
     r"(?:像|如同|好比|犹如|相当于)[^，。！？\n]{0,6}一[位名个][^，。！？\n]{0,14}"
     r"(?:导师|秘书|助手|顾问|管家|审查员|实习生|军师|教练|伙伴|专家|舵手|灯塔)",
     "0.002", "换成这东西实际做了什么。见规则6"),
    ("X", "概括替代(已否决)",
     r"(?:显著(?:提升|提高|增长|改善|增加|优势)|大幅(?:提升|增长|提高|改善|下降|减少)"
     r"|明显(?:改善|提升|优势|变化)|效率的提升|众多|海量)",
     "—", "2026-10-13 对称口径复查净零（AI 更含糊 24.7% vs 更具体 26.0%，数字保留 98%），"
     "即使同段有具体数值也不改；改写的保真由信息守恒原则兜底"),
    # ---- 已否决特征：统计并展示，但明确标不改，防过度清理 ----
    ("X", "序数词小标题(已否决)",
     r"(?:^|\n)\s{0,3}#{1,6}\s{0,3}[一二三四五六七八九十][、.]",
     "—", "实测人类比 AI 更常用（8.6% vs 4.9%），不是 AI 味，不改"),
    ("X", "「这意味着」复述(已否决)",
     r"(?:这意味着|这表明|这说明)",
     "—", "配对复测人类更多，三项口径全反向，不改"),
    ("X", "空转句引列表(已否决)",
     r"[^，。！？\n]{0,25}[：:]\s*(?:\n|$)",
     "—", "配对复测人类高一个量级（目录式长文的正常写法），不改"),
]

# 分号/破折号/引号按字符计，不走逐行命中
CHAR_HITS = [
    ("F", "破折号", "——", "0.80", "密度>2/千字优先处理；可安全改的局部用法默认建议改，保留须说明功能"),
    ("F", "分号", "；", "—", "GPT 指纹（δ+0.80）；可安全拆句时默认建议改，保留须说明层级作用"),
    ("F", "引号", "“", "—", "Opus 偏少（δ−0.67）；引号少不必然是问题，报告用"),
]

# 同义词轮换组（用词不敢重复的启发式检测，B级）
SYN_GROUPS = [
    ("使用", "采用", "运用", "利用", "借助"),
    ("方法", "方式", "途径", "路径", "做法"),
    ("提升", "提高", "增强", "强化", "优化"),
    ("显示", "表明", "揭示", "反映", "说明"),
    ("重要", "关键", "核心", "至关重要"),
    ("问题", "难题", "挑战", "困境", "痛点"),
    ("帮助", "协助", "助力", "支持"),
]

# 阈值 [可调]：换语料后重标
TH_SENT_CV = 0.55      # 句长CV低于此 → 节奏偏均匀（v1实测 人类0.67 / AI0.58）
TH_SECT_CV = 0.45      # 节长CV低于此 → 节长偏均匀
TH_HEAD_KK = 0.50      # 每千字小标题超过此 → 切得偏碎
TH_ISO_100P = 8.0      # 每百段两句同构超过此 → 同构偏多（人类4.81 / AI9.41）

# 人类参考线（270 对配对实测中位值，见 Downloads/分析结果/配对指标结果-按模型分列.csv）。
# ref 形如 "0.80"（人类中位/千字）或 "4.81/AI9.41"；两侧超界都算偏离（双侧计分）。
HUMAN_REF = {
    "句长CV":      {"ref": "0.54",  "ai": "0.46",  "note": "人类忽长忽短；低于参考=节奏均匀", "方向": "低"},
    "节长CV":      {"ref": "0.83",  "ai": "0.31",  "note": "人类节长参差；低于参考=节节等长", "方向": "低"},
    "小标题/千字": {"ref": "0.32",  "ai": "1.26",  "note": "人类整篇连写；高于参考=切得碎", "方向": "高"},
    "两句同构/百段": {"ref": "5.52", "ai": "8.71", "note": "第一层指标4（两句版），中等效应", "方向": "高"},
    "三句同构/百段": {"ref": "0.41*","ai": "0.84*", "note": "*为启发式粗估，语义判读见判据文件", "方向": "高"},
    "mtld粗估":    {"ref": "143",    "ai": "227",  "note": "高=换词多；AI 高于人类=不敢重复", "方向": "高"},
    "破折号":      {"ref": "0.83",  "ai": "2.02",  "note": "Opus 指纹 +0.95 / GPT −0.54，方向相反", "方向": "分模型"},
    "分号":        {"ref": "0.77",  "ai": "1.51",  "note": "GPT 指纹 δ+0.80；Opus −0.11 无差", "方向": "分模型"},
    "引号":        {"ref": "20.0",  "ai": "2.7",   "note": "Opus 偏少 δ−0.67；报告用，不改", "方向": "低"},
    "顿号":        {"ref": "6.12",  "ai": "8.24",  "note": "第一层密集并列（句内塞多项）", "方向": "高"},
    "冒号":        {"ref": "3.59",  "ai": "2.70",  "note": "总量人类更多；只有「结论提示」子类是真信号，语义层判", "方向": "低"},
}

# ---------------- 切分 ----------------

HEADING = re.compile(r"^#{1,6}\s")
BOLD_LINE = re.compile(r"^\*\*[^*]{2,40}\*\*$")
LIST_LINE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s")
QUOTE_LINE = re.compile(r"^>")
FENCE = re.compile(r"^```")
TABLE_LINE = re.compile(r"^\|")

COMMENT = re.compile(
    r"^(?:听起来|看起来|看上去|听上去|说白了|说到底|换句话说|意味着|值得注意|"
    r"不难看出|细看|再看|回过头看|问题在于|原因在于|结果是|有意思的是|"
    r"更重要的是|关键在于|真正的)")


def hanzi(s):
    return len(re.findall(r"[一-鿿]", s))


def split_sents(para):
    return [s.strip() for s in re.split(r"[。！？；]", para) if len(s.strip()) >= 4]


def signature(sent):
    """句结构指纹：逗号数、有无冒号、有无括号、长度档（沿用第一版，经复测）"""
    return (sent.count("，"), "：" in sent or ":" in sent,
            ("（" in sent or "(" in sent), len(sent) // 15)


def isomorphic_triples(text):
    """三连同构候选（供语义层判读）：signature 粗筛出的连续三句，
    每组带行号与三句原文。粗筛宽（部分同构也收），判读由 Claude 按
    「高度同构」判据收紧——270 对实测：宽口径 AI 71.1% vs 人类 56.2%
    无区分力，只有高度同构档有 2.76× 差异。"""
    out = []
    for kind, body, first_no in paragraph_blocks(text):
        if kind != "prose":
            continue
        sents = [s for s in split_sents(body) if len(s) > 10]
        for i in range(len(sents) - 2):
            sigs = [signature(s) for s in sents[i:i + 3]]
            if all(s == sigs[0] for s in sigs) and sigs[0][0] >= 1:
                out.append({"line": first_no,
                            "sents": sents[i:i + 3]})
    return out


def isomorphic_hits(para, n):
    sents = [s for s in split_sents(para) if len(s) > 10]
    hits = []
    for i in range(len(sents) - n + 1):
        sigs = [signature(s) for s in sents[i:i + n]]
        if all(s == sigs[0] for s in sigs) and sigs[0][0] >= 1:
            hits.append("／".join(sents[i:i + n]))
    return hits


def paragraph_blocks(text):
    """按空行切块并分类，返回 [(kind, block_text, first_line_no)]"""
    blocks, cur, cur_kind, start = [], [], None, None
    in_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            cur.append(line)
            continue
        if not in_fence and not line.strip():
            if cur:
                blocks.append((cur_kind or "prose", "\n".join(cur), start))
                cur, cur_kind, start = [], None, None
            continue
        if not cur:
            start = no
        cur.append(line)
        if in_fence:
            cur_kind = cur_kind or "code"
        elif HEADING.match(line):
            cur_kind = "heading"
        elif QUOTE_LINE.match(line):
            cur_kind = cur_kind or "quote"
        elif TABLE_LINE.match(line):
            cur_kind = cur_kind or "table"
        elif LIST_LINE.match(line):
            cur_kind = cur_kind or "list"
        elif BOLD_LINE.match(line) and cur_kind is None:
            cur_kind = "heading"
    if cur:
        blocks.append((cur_kind or "prose", "\n".join(cur), start))
    return blocks


def mtld(toks, threshold=0.72, min_len=10):
    """词汇多样性 MTLD 的近似（中文无分词，用二字组当伪词，粗估）"""
    if len(toks) < min_len * 4:
        return None

    def pass_factors(seq):
        factors, types, count = 0.0, set(), 0
        for t in seq:
            count += 1
            types.add(t)
            if count >= min_len and len(types) / count <= threshold:
                factors += 1
                types, count = set(), 0
        if count:
            factors += (1 - len(types) / count) / (1 - threshold)
        return max(factors, 1e-9)

    f, r = pass_factors(toks), pass_factors(toks[::-1])
    return round(len(toks) / 2 * (1 / f + 1 / r))


def cv(vals):
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    if m == 0:
        return None
    var = sum((v - m) ** 2 for v in vals) / len(vals)
    return (var ** 0.5) / m


# ---------------- 度量 ----------------

def measure_docs(docs):
    total_han = 0
    regex_hits = {name: [] for _, name, *_ in REGEX_HITS}
    char_counts = {name: 0 for _, name, *_ in CHAR_HITS}
    syn_hits = []
    n_para = n_head = 0
    iso2 = iso3 = 0
    sent_lens, sect_lens = [], []
    all_bigrams = []

    for fname, text in docs:
        lines = text.splitlines()
        # 逐行正则命中（跳过代码围栏内）
        in_fence = False
        for no, line in enumerate(lines, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for _, name, pat, *_ in REGEX_HITS:
                for m in re.finditer(pat, line):
                    excerpt = m.group(0)
                    regex_hits[name].append(
                        {"file": fname, "line": no, "excerpt": excerpt[:60]})
        for _, name, ch, *_ in CHAR_HITS:
            char_counts[name] += text.count(ch)

        # 结构
        blocks = paragraph_blocks(text)
        sect_chars = 0
        for kind, body, first_no in blocks:
            if kind == "heading":
                n_head += 1
                if sect_chars > 0:
                    sect_lens.append(sect_chars)
                sect_chars = 0
                continue
            if kind != "prose":
                continue
            n_para += 1
            h = hanzi(body)
            sect_chars += len(body)
            for s in split_sents(body):
                sent_lens.append(hanzi(s) or len(s))
            iso2 += len(isomorphic_hits(body, 2))
            iso3 += len(isomorphic_hits(body, 3))
            all_bigrams.extend(
                body[i:i + 2] for i in range(len(body) - 1) if hanzi(body[i:i + 2]) == 2)
        if sect_chars > 0:
            sect_lens.append(sect_chars)

        # 同义词轮换（段内 ≥2 个不同组员）
        for kind, body, first_no in blocks:
            if kind != "prose":
                continue
            for group in SYN_GROUPS:
                found = [w for w in group if w in body]
                if len(found) >= 2:
                    syn_hits.append({"file": fname, "line": first_no,
                                     "excerpt": "／".join(found),
                                     "context": body[:70]})
        total_han += hanzi(text)

    kk = total_han / 1000 or 1
    sent_cv = cv(sent_lens) if sent_lens else None
    sect_cv = cv(sect_lens) if len(sect_lens) >= 3 else None

    return {
        "meta": {
            "篇数": len(docs), "万汉字": round(total_han / 10000, 2),
            "段数": n_para, "小标题数": n_head,
        },
        "density": {name: round(n / kk, 3) for name, n in
                    [(nm, len(v)) for _, nm, *_ in REGEX_HITS for v in [regex_hits[nm]]]},
        "char_density": {name: round(n / kk, 3) for name, n in char_counts.items()},
        "hits": regex_hits,
        "syn_hits": syn_hits,
        "structure": {
            "句长CV": round(sent_cv, 3) if sent_cv else None,
            "节长CV": round(sect_cv, 3) if sect_cv else None,
            "小标题/千字": round(n_head / kk, 3),
            "两句同构/百段": round(iso2 / n_para * 100, 2) if n_para else None,
            "三句同构/百段": round(iso3 / n_para * 100, 2) if n_para else None,
            "mtld粗估": mtld(all_bigrams),
        },
    }


# ---------------- 语义层候选抽取 ----------------

def first_prose_blocks(text, max_gap=2):
    """按空行分块的 prose 块（去掉标题/代码/表格），max_gap 行以内算同块。"""
    return [(b, n) for kind, b, n in paragraph_blocks(text) if kind == "prose"]


NOISE_RE = re.compile(r"\]\(|\]\s*\(|\||^!|^中文\s*\|")


def clean_para(b):
    """去掉 markdown 强调/链接语法后返回纯文本，噪声行（导航/表格/图片）返回空。"""
    if NOISE_RE.search(b[:200]):
        return ""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", b)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*`_#>]", "", t)
    return t.strip()


CAND_CAPS = {"rename": 60, "cohesion": 60, "colon": 80, "iso3": 60}  # 长文防爆，超出截断并标 truncated


def extract_candidates(docs):
    """四类语义层候选。每条带判据类型，供会话内 Claude 按
    references/semantic-criteria.md 逐条封闭判断（标签+置信度），
    判断结果写回同结构 JSON 的 label/confidence/reason 字段。"""
    rename, cohesion, colon, iso3 = [], [], [], []
    for fname, text in docs:
        blocks = [(clean_para(b), no) for b, no in first_prose_blocks(text)]
        blocks = [(b, no) for b, no in blocks if hanzi(b) >= 20]
        # 1) 同义重命名：段级（每段一条候选，判「换了几次实义说法」）
        for b, no in blocks:
            if hanzi(b) >= 30:
                rename.append({"type": "rename", "file": fname, "line": no, "para": b})
        # 2) 衔接连环：段间接口（上段末句 + 下段首句）
        for i in range(len(blocks) - 1):
            a, b = blocks[i][0], blocks[i + 1][0]
            tail = split_sents(a) or [a[-60:]]
            head = split_sents(b) or [b[:60]]
            cohesion.append({"type": "cohesion",
                             "file": fname, "line": blocks[i + 1][1],
                             "prev_tail": tail[-1], "next_head": head[0]})
        # 3) 冒号句：正文冒号（引号内/标题/列表行除外）
        in_fence = False
        for no, line in enumerate(text.splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or HEADING.match(line) or LIST_LINE.match(line) or NOISE_RE.search(line):
                continue
            for m in re.finditer(r"([^：:，。！？\n]{2,30})[：:](.{2,60})", line):
                colon.append({"type": "colon",
                              "file": fname, "line": no,
                              "colon_before": m.group(1), "colon_after": m.group(2)[:60],
                              "sentence": line.strip()[:120]})
        # 4) 三连同构：signature 粗筛 + Claude 判高度同构
        iso3.extend(dict(c, file=fname) for c in isomorphic_triples(text))
    all_c = {"rename": rename, "cohesion": cohesion, "colon": colon, "iso3": iso3}
    truncated = {k: len(v) > cap for k, v, cap in
                 ((k, v, CAND_CAPS[k]) for k, v in all_c.items())}
    meta = {"n_candidates": sum(min(len(v), CAND_CAPS[k]) for k, v in all_c.items())}
    meta.update({f"n_{k}": len(v) for k, v in all_c.items()})
    meta["truncated"] = {k: cap for k, cap in CAND_CAPS.items() if truncated[k]} or False
    if meta["truncated"]:
        # 均匀抽样保留候选（跳读不偏头部），判读覆盖率为截断后条数/总条数
        for k, cap in CAND_CAPS.items():
            if truncated[k]:
                step = len(all_c[k]) / cap
                all_c[k] = [all_c[k][int(i * step)] for i in range(cap)]
    return {"meta": meta,
            "rename": all_c["rename"], "cohesion": all_c["cohesion"],
            "colon": all_c["colon"], "iso3": all_c["iso3"]}


# ---------------- 报告 ----------------

def fmt_report(r, max_hits):
    out = ["去AI味检测报告（v2，只检测不改写）", ""]
    m = r["meta"]
    out.append(f"语料：{m['篇数']} 篇 / {m['万汉字']} 万汉字 / {m['段数']} 段 / {m['小标题数']} 个小标题")
    out.append("")

    def emit(level, title):
        rows = [(nm, ref, adv) for lv, nm, _, ref, adv in REGEX_HITS if lv == level]
        hits = r["hits"]
        dens = r["density"]
        any_row = False
        sec = [f"[{level}] {title}"]
        for nm, ref, adv in rows:
            n = len(hits.get(nm, []))
            d = dens.get(nm, 0)
            if n == 0:
                continue
            any_row = True
            ref_s = f"（人类≈{ref}/千字）" if ref != "—" else ""
            sec.append(f"  {nm}：{n} 处，{d}/千字{ref_s}")
            sec.append(f"    → {adv}")
            for h in hits[nm][:max_hits]:
                sec.append(f"      · {h['file']}:{h['line']}  {h['excerpt']}")
        if any_row:
            out.extend(sec)
            out.append("")
        return any_row

    emit("A", "机械改候选（模型复核后建议，用户回复后改）")
    emit("B", "建议改候选（模型逐条筛选，用户回复后改）")
    emit("C", "只报告（默认不改）")
    emit("H", "人审区（默认保留，用户主动要求时再审）")
    emit("X", "已否决特征（实测不是 AI 味，仅展示计数——不要改）")

    # 指纹
    sec = ["[F] 指纹（分模型特征，解读必须带方向）"]
    for _, nm, _, ref, adv in CHAR_HITS:
        d = r["char_density"].get(nm, 0)
        sec.append(f"  {nm}：{d}/千字" + (f"（人类≈{ref}）" if ref != "—" else ""))
        sec.append(f"    → {adv}")
    out.extend(sec)
    out.append("")

    # 同义词轮换
    if r["syn_hits"]:
        out.append("[B] 用词不敢重复（同义词轮换启发式，误报可能，逐条复核）")
        for h in r["syn_hits"][:max_hits * 2]:
            out.append(f"  · {h['file']}:{h['line']}  轮换：{h['excerpt']}")
            out.append(f"    {h['context']}")
        out.append("")

    # 结构
    s = r["structure"]
    out.append("[C] 结构与节奏（对照人类参考线，偏离才提示；箭头=往哪个方向偏算问题）")
    flags = []
    if s["句长CV"] is not None and s["句长CV"] < TH_SENT_CV:
        ref = HUMAN_REF["句长CV"]
        flags.append(f"句长CV={s['句长CV']}（人类中位{ref['ref']} / AI {ref['ai']}，偏低=节奏均匀）")
    if s["节长CV"] is not None and s["节长CV"] < TH_SECT_CV:
        ref = HUMAN_REF["节长CV"]
        flags.append(f"节长CV={s['节长CV']}（人类中位{ref['ref']} / AI {ref['ai']}，偏低=节长均匀）")
    if s["小标题/千字"] > TH_HEAD_KK:
        ref = HUMAN_REF["小标题/千字"]
        flags.append(f"小标题{s['小标题/千字']}/千字（人类中位{ref['ref']} / AI {ref['ai']}，偏高=切得碎）")
    if s["两句同构/百段"] is not None and s["两句同构/百段"] > TH_ISO_100P:
        ref = HUMAN_REF["两句同构/百段"]
        flags.append(f"两句同构{s['两句同构/百段']}/百段（人类{ref['ref']} / AI {ref['ai']}，偏高）")
    if s["三句同构/百段"] and s["三句同构/百段"] > 0.8:
        ref = HUMAN_REF["三句同构/百段"]
        flags.append(f"三句同构{s['三句同构/百段']}/百段（人类{ref['ref']} / AI {ref['ai']}，偏高；判读见判据文件）")
    for f_ in flags:
        out.append(f"  ⚠ {f_}")
    if not flags:
        out.append("  （结构节奏各项均在参考区间内）")
    if s["mtld粗估"]:
        ref = HUMAN_REF["mtld粗估"]
        out.append(f"  mtld粗估={s['mtld粗估']}（人类中位≈{ref['ref']} / AI≈{ref['ai']}；高于人类=换词多不敢重复；粗估，仅供参考）")
    out.append("")
    out.append("处理顺序建议：先A后B；C级项改写需要动结构或补信息，"
               "超出白名单边界，只在用户明确要求时另议。")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="文件或目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--max-hits", type=int, default=5, help="每项最多列出的命中数")
    ap.add_argument("--candidates", action="store_true",
                    help="抽取语义层候选（rename/cohesion/colon/iso3），不跑常规检测")
    ap.add_argument("--out", help="候选 JSON 输出路径（默认 stdout）")
    args = ap.parse_args()

    p = Path(args.target)
    if not p.exists():
        print(f"路径不存在：{p}", file=sys.stderr)
        sys.exit(1)
    docs = []
    if p.is_file():
        docs.append((p.name, p.read_text(encoding="utf-8", errors="ignore")))
    else:
        for f in sorted(p.rglob("*")):
            if f.suffix.lower() in EXTS and f.is_file():
                docs.append((str(f.relative_to(p)),
                             f.read_text(encoding="utf-8", errors="ignore")))
    if not docs:
        print("未找到 .md/.txt 文件", file=sys.stderr)
        sys.exit(1)

    if args.candidates:
        c = extract_candidates(docs)
        payload = json.dumps(c, ensure_ascii=False, indent=1)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
            n = c["meta"]["n_candidates"]
            print(f"候选 {n} 条 → {args.out}"
                  f"（rename {c['meta']['n_rename']} / cohesion {c['meta']['n_cohesion']}"
                  f" / colon {c['meta']['n_colon']} / iso3 {c['meta']['n_iso3']}）")
        else:
            print(payload)
        return

    r = measure_docs(docs)
    if r["meta"]["万汉字"] < 0.05:
        print("汉字过少（<500），检测无意义", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(fmt_report(r, args.max_hits))


if __name__ == "__main__":
    main()
