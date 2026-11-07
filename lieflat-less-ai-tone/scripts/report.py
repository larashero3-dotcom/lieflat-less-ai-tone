#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去AI味 v2 · 前后对比报告：指标前后对比 + 分级问题清单 + 标记前后对照。

默认输出 Markdown 报告（与用户文稿同格式，md 标记原样保留，
可直接复制回写作流程；`--format html` 生成单文件网页版）。

用法（改动前后各跑一次 detect.py --json，再生成报告）：
    python3 scripts/detect.py 原文.md --json > /tmp/before.json
    python3 scripts/detect.py 改后.md --json > /tmp/after.json
    python3 scripts/report.py 原文.md 改后.md /tmp/before.json /tmp/after.json \
        [--semantic 判读结果.json] [--out 报告.md] [--format md|html]

--semantic 可选：detect.py --candidates 抽取的候选经 Claude 按
references/semantic-criteria.md 判读后的 JSON（条目带 label/confidence/reason）。

纯标准库，无外部依赖。
md 版对照约定：~~灰色删除~~ = 被改掉原文，**加粗** = 改后新文字。
"""
import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from detect import REGEX_HITS  # 名字 → 级别映射（A/B/H/X）

# ---------------- 指标呈现配置 ----------------

# HTML 顶部指标对比表：键 → (展示名, 方向说明, 人类参考)
# 参考值来自 270 对配对实测中位值（见仓库根目录 RESEARCH.md / 配对指标结果 CSV）。
METRIC_ROWS = [
    ("翻案腔", "不是A而是B 对举", "低", 0.22),
    ("提示语冒号", "结论提示冒号", "低", 0.08),
    ("顿号并列≥3", "密集并列", "低", 1.78),
    ("过长前置定语", "前置定语长", "低", 0.1),
]

STRUCT_ROWS = [
    ("句长CV", "句长起伏", "越高越参差", "人类≈0.54 / AI≈0.46"),
    ("节长CV", "节长参差", "越高越参差", "人类≈0.83 / AI≈0.31"),
    ("小标题/千字", "分节密度", "越低越整篇连写", "人类≈0.32 / AI≈1.26"),
    ("两句同构/百段", "相邻句同构", "越低越好", "人类≈5.52 / AI≈8.71"),
    ("三句同构/百段", "三连同构(粗筛)", "越低越好", "人类≈0.41 / AI≈0.84"),
    ("mtld粗估", "换词多样性", "低于人类≈自然", "人类≈143 / AI≈227"),
]

FINGERPRINT_ROWS = [
    ("破折号", "Opus 狂用 +0.95 / GPT 少用 −0.54，方向相反分模型看"),
    ("分号", "GPT 指纹 δ+0.80；Opus 无差"),
    ("引号", "Opus 偏少 δ−0.67，报告用不改"),
]

CSS = """
body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:760px;margin:40px auto;line-height:1.9;font-size:16px;padding:0 20px;color:#222}
h1{font-size:22px}h2{font-size:19px;border-bottom:2px solid #ccc;padding-bottom:6px;margin-top:2.2em}
h3{font-size:16px;margin-bottom:0.4em}
table{border-collapse:collapse;width:100%;font-size:14px;margin:0.6em 0 1.4em}
th,td{border:1px solid #ddd;padding:5px 10px;text-align:left;vertical-align:top}
th{background:#f5f5f5}
.warn{background:#fff3cd;padding:14px 18px;border-radius:8px;margin-bottom:1.5em;font-size:14px}
.legend{color:#555;margin-bottom:2em;font-size:14px}
.chg,.ins{color:#d32f2f;font-weight:600}
.del{color:#aaa;text-decoration:line-through}
.up{color:#c62828;font-weight:600}.down{color:#2e7d32;font-weight:600}.flat{color:#777}
.tagA{background:#e3f2fd;padding:1px 7px;border-radius:4px;font-size:12px}
.tagB{background:#fff3e0;padding:1px 7px;border-radius:4px;font-size:12px}
.tagC{background:#f3e5f5;padding:1px;border-radius:4px;font-size:12px}
.tagF{background:#eceff1;padding:1px 7px;border-radius:4px;font-size:12px}
.tagX{background:#fafafa;color:#888;padding:1px 7px;border-radius:4px;font-size:12px}
.tagH{background:#fce4ec;padding:1px 7px;border-radius:4px;font-size:12px}
.small{color:#777;font-size:13px}
.human{color:#2e7d32}
details{margin:0.3em 0}
summary{cursor:pointer}
p{margin:0 0 1.1em}
"""


def esc(s):
    return html.escape(str(s), quote=False)


def arrow(before, after, better="low"):
    """better: 'low'=数值低更好, 'high'=数值高更好, None=不判方向"""
    if before is None or after is None or before == after:
        cls, mark = "flat", "→"
    elif better == "low":
        cls, mark = ("down", "↓") if after < before else ("up", "↑")
    elif better == "high":
        cls, mark = ("up", "↑") if after > before else ("down", "↓")
    else:
        cls, mark = "flat", "→"
    return f'<span class="{cls}">{mark}</span>'


# ---------------- 指标对比表 ----------------

def metric_table(d0, d1):
    rows = []
    for key, name, better, ref in METRIC_ROWS:
        v0 = d0["density"].get(key)
        v1 = d1["density"].get(key)
        rows.append(f"<tr><td>{esc(name)}</td>"
                    f"<td>{v0 if v0 is not None else '—'}</td>"
                    f"<td>{v1 if v1 is not None else '—'}</td>"
                    f"<td>{arrow(v0, v1, better)}</td>"
                    f'<td class="human">≈{ref}</td></tr>')
    for key, name, better, ref in STRUCT_ROWS:
        v0 = d0["structure"].get(key)
        v1 = d1["structure"].get(key)
        rows.append(f"<tr><td>{esc(name)}</td>"
                    f"<td>{v0 if v0 is not None else '—'}</td>"
                    f"<td>{v1 if v1 is not None else '—'}</td>"
                    f"<td>{arrow(v0, v1, better)}</td>"
                    f'<td class="human">{esc(ref)}</td></tr>')
    for key, note in FINGERPRINT_ROWS:
        v0 = d0["char_density"].get(key)
        v1 = d1["char_density"].get(key)
        rows.append(f"<tr><td>{esc(key)}<span class='small'>（指纹）</span></td>"
                    f"<td>{v0}</td><td>{v1}</td><td>{arrow(v0, v1, None)}</td>"
                    f'<td class="small">{esc(note)}</td></tr>')
    return ("<table><tr><th>指标</th><th>改前</th><th>改后</th><th>变化</th>"
            "<th>人类参考</th></tr>" + "".join(rows) + "</table>"
            '<p class="small">↓/↑ 绿色=向人类参考方向改善，红色=恶化；指纹行不判方向。'
            "参考值=270 对同题配对实测人类中位（每千字或 CV 值），见 RESEARCH.md。</p>")


# ---------------- 分级问题清单 ----------------

def findings_section(d):
    out = []
    for lvl, title, cls in [("A", "机械改（模型复核误报后处理）", "tagA"),
                            ("B", "建议改（模型逐条筛选后处理）", "tagB"),
                            ("H", "人审区（默认保留，用户主动要求时再审）", "tagH"),
                            ("X", "已否决特征（实测不是 AI 味——不要改）", "tagX")]:
        names = [nm for lv, nm, *_ in REGEX_HITS if lv == lvl]
        rows = []
        for nm in names:
            hs = d["hits"].get(nm, [])
            if not hs:
                continue
            rows.append(f"<div><strong>{esc(nm)}</strong> {len(hs)} 处")
            rows.append("<details><summary class='small'>展开命中</summary>")
            for h in hs[:20]:
                rows.append(f"<p class='small'>{esc(h['file'])}:{h['line']}　"
                            f"{esc(h['excerpt'])}</p>")
            rows.append("</details></div>")
        if rows:
            out.append(f'<h3><span class="{cls}">{lvl}</span> {esc(title)}</h3>')
            out.extend(rows)
    return "\n".join(out)


def semantic_section(sem):
    """语义层判读结果：四项各自小结 + 明细折叠。"""
    if not sem:
        return ""
    out = ['<h2>语义层判读（会话内模型按实验判据逐条判断）</h2>',
           '<p class="small">四项在 270 对配对语料统计显著；同义重命名为单模型判据（弱一档）。'
           '判据见 references/semantic-criteria.md。</p>']
    groups = {"rename": "同义重命名（段级）", "cohesion": "衔接方式（段间接口）",
              "colon": "冒号分类", "iso3": "高度同构三连"}
    for key, title in groups.items():
        items = [c for c in sem.get(key, []) if c.get("label")]
        if not items:
            continue
        counts = {}
        for c in items:
            counts[c["label"]] = counts.get(c["label"], 0) + 1
        stats = "，".join(f"{esc(k)} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
        out.append(f"<h3>{esc(title)} <span class='small'>{len(items)} 条：{stats}</span></h3>")
        flagged = [c for c in items if c.get("label") in {
            "2组", "3组及以上",                      # 重命名重灾
            "明确承接",                              # 衔接连环（连续长度另算）
            "结论提示",                              # 冒号真信号
            "高度同构",                              # 同构真信号
        }]
        # 衔接连环长度
        chain_note = ""
        if key == "cohesion":
            labels = [c.get("label") for c in items]
            best = cur = 0
            for lb in labels:
                cur = cur + 1 if lb == "明确承接" else 0
                best = max(best, cur)
            chain_note = f"（最长连环 {best} 个接口；≥6 为 AI 特征，人类中位 2）"
            if best >= 6:
                chain_note = f'<span class="up">⚠ {chain_note}</span>'
        if key == "cohesion" and chain_note:
            out.append(f"<p>{chain_note}</p>")
        for c in flagged[:15]:
            text = c.get("para") or " → ".join(filter(None, [
                c.get("prev_tail"), c.get("next_head")])) or c.get("sentence") \
                or "／".join(c.get("sents") or [])
            conf = c.get("confidence", "")
            reason = c.get("reason", "")
            out.append(f"<p class='small'><strong>{esc(c['label'])}</strong>"
                       f"（置信:{esc(conf)}）{esc(c.get('file',''))}:{c.get('line','')}　"
                       f"{esc(text[:110])}"
                       + (f"<br>理由：{esc(reason[:100])}" if reason else "") + "</p>")
    return "\n".join(out)


# ---------------- 标红 diff ----------------

def para_split(text):
    """按空行分段，保留原文形态（不去 markdown 标记）。"""
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras


def inline_diff(a, b):
    """段内字符级 diff：相同=黑，删=灰删除线，改/增=红。"""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(esc(a[i1:i2]))
        elif tag == "delete":
            out.append(f'<span class="del">{esc(a[i1:i2])}</span>')
        elif tag == "insert":
            out.append(f'<span class="ins">{esc(b[j1:j2])}</span>')
        elif tag == "replace":
            out.append(f'<span class="del">{esc(a[i1:i2])}</span>'
                       f'<span class="chg">{esc(b[j1:j2])}</span>')
    return "".join(out)


def diff_section(text0, text1):
    p0, p1 = para_split(text0), para_split(text1)
    sm = difflib.SequenceMatcher(None, p0, p1, autojunk=False)
    body = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for p in p0[i1:i2]:
                body.append(f"<p>{esc(p)}</p>")
        elif tag == "delete":
            for p in p0[i1:i2]:
                body.append(f'<p><span class="del">{esc(p)}</span></p>')
        elif tag == "insert":
            for p in p1[j1:j2]:
                body.append(f'<p><span class="ins">{esc(p)}</span></p>')
        elif tag == "replace":
            for pa, pb in zip(p0[i1:i2], p1[j1:j2]):
                body.append(f"<p>{inline_diff(pa, pb)}</p>")
            # 段数不等时多出的段落单独标
            for p in p0[i1 + (j2 - j1):i2]:
                body.append(f'<p><span class="del">{esc(p)}</span></p>')
            for p in p1[j1 + (i2 - i1):j2]:
                body.append(f'<p><span class="ins">{esc(p)}</span></p>')
    return "\n".join(body)


# ---------------- Markdown 报告 ----------------

def arrow_md(before, after, better="low"):
    if before is None or after is None or before == after:
        return "→"
    if better == "low":
        return "↓" if after < before else "↑"
    if better == "high":
        return "↑" if after > before else "↓"
    return "→"


def metric_table_md(d0, d1):
    rows = ["| 指标 | 改前 | 改后 | 变化 | 人类参考 |", "|---|---|---|---|---|"]
    for key, name, better, ref in METRIC_ROWS:
        v0 = d0["density"].get(key)
        v1 = d1["density"].get(key)
        rows.append(f"| {name} | {v0 if v0 is not None else '—'} | "
                    f"{v1 if v1 is not None else '—'} | {arrow_md(v0, v1, better)} | ≈{ref} |")
    for key, name, better, ref in STRUCT_ROWS:
        v0 = d0["structure"].get(key)
        v1 = d1["structure"].get(key)
        rows.append(f"| {name} | {v0 if v0 is not None else '—'} | "
                    f"{v1 if v1 is not None else '—'} | {arrow_md(v0, v1, better)} | {ref} |")
    for key, note in FINGERPRINT_ROWS:
        v0 = d0["char_density"].get(key)
        v1 = d1["char_density"].get(key)
        rows.append(f"| {key}（指纹） | {v0} | {v1} | {arrow_md(v0, v1, None)} | {note} |")
    rows.append("")
    rows.append("↓/↑ = 向人类参考方向改善/恶化；指纹行不判方向。"
                "参考值=270 对同题配对实测人类中位（每千字或 CV 值），见 RESEARCH.md。")
    return "\n".join(rows)


def findings_section_md(d):
    out = []
    for lvl, title in [("A", "机械改（模型复核误报后处理）"),
                       ("B", "建议改（模型逐条筛选后处理）"),
                       ("H", "人审区（默认保留，用户主动要求时再审）"),
                       ("X", "已否决特征（实测不是 AI 味——不要改）")]:
        names = [nm for lv, nm, *_ in REGEX_HITS if lv == lvl]
        blocks = []
        for nm in names:
            hs = d["hits"].get(nm, [])
            if not hs:
                continue
            lines = [f"**{nm}** {len(hs)} 处", ""]
            for h in hs[:20]:
                lines.append(f"- `{h['file']}:{h['line']}`　{h['excerpt']}")
            lines.append("")
            blocks.append("\n".join(lines))
        if blocks:
            out.append(f"### {lvl} 级 · {title}\n")
            out.extend(blocks)
    return "\n".join(out)


def semantic_section_md(sem):
    if not sem:
        return ""
    out = ["## 语义层判读（会话内模型按实验判据逐条判断）", "",
           "四项在 270 对配对语料统计显著；同义重命名为单模型判据（弱一档）。"
           "判据见 references/semantic-criteria.md。", ""]
    groups = {"rename": "同义重命名（段级）", "cohesion": "衔接方式（段间接口）",
              "colon": "冒号分类", "iso3": "高度同构三连"}
    for key, title in groups.items():
        items = [c for c in sem.get(key, []) if c.get("label")]
        if not items:
            continue
        counts = {}
        for c in items:
            counts[c["label"]] = counts.get(c["label"], 0) + 1
        stats = "，".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
        out.append(f"### {title}（{len(items)} 条：{stats}）")
        out.append("")
        if key == "cohesion":
            labels = [c.get("label") for c in items]
            best = cur = 0
            for lb in labels:
                cur = cur + 1 if lb == "明确承接" else 0
                best = max(best, cur)
            note = f"最长连环 {best} 个接口；≥6 为 AI 特征，人类中位 2。"
            if best >= 6:
                note = f"⚠ {note}"
            out.append(note)
            out.append("")
        flagged = [c for c in items if c.get("label") in {
            "2组", "3组及以上", "明确承接", "结论提示", "高度同构",
        }]
        for c in flagged[:15]:
            text = c.get("para") or " → ".join(filter(None, [
                c.get("prev_tail"), c.get("next_head")])) or c.get("sentence") \
                or "／".join(c.get("sents") or [])
            conf = c.get("confidence", "")
            reason = c.get("reason", "")
            out.append(f"- **{c['label']}**（置信:{conf}）`{c.get('file','')}:{c.get('line','')}`　{text[:110]}"
                       + (f"　理由：{reason[:100]}" if reason else ""))
        out.append("")
    return "\n".join(out)


def inline_diff_md(a, b):
    """段内字符级 diff 的 md 版：<del> = 原文，<ins> = 新文字。

    用 HTML 行内标签而非 ~~/**：改动经常落在原有 **加粗**、## 标题等
    md 标记内部或旁边，~~/** 会跟原文标记配对错乱（嵌套碎掉）；
    <del>/<ins> 是 md 合法行内 HTML，跟任何 md 标记零字符冲突，
    Typora/VS Code/GitHub 预览均正常渲染（删除线/下划线）。
    """
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(a[i1:i2])
        elif tag == "delete":
            out.append(f"<del>{a[i1:i2]}</del>")
        elif tag == "insert":
            out.append(f"<ins>{b[j1:j2]}</ins>")
        else:  # replace
            out.append(f"<del>{a[i1:i2]}</del><ins>{b[j1:j2]}</ins>")
    return "".join(out)


def diff_section_md(text0, text1):
    p0, p1 = para_split(text0), para_split(text1)
    sm = difflib.SequenceMatcher(None, p0, p1, autojunk=False)
    body = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            body.extend(p0[i1:i2])
        elif tag == "delete":
            body.extend(f"<del>{p}</del>" for p in p0[i1:i2])
        elif tag == "insert":
            body.extend(f"<ins>{p}</ins>" for p in p1[j1:j2])
        elif tag == "replace":
            for pa, pb in zip(p0[i1:i2], p1[j1:j2]):
                body.append(inline_diff_md(pa, pb))
            for p in p0[i1 + (j2 - j1):i2]:
                body.append(f"<del>{p}</del>")
            for p in p1[j1 + (i2 - i1):j2]:
                body.append(f"<ins>{p}</ins>")
    return "\n\n".join(body)


def build_report_md(t0, t1, d0, d1, sem, name0, name1):
    parts = [
        "# 去AI味 · 前后对比报告",
        "",
        f"{name0} → {name1}",
        "",
        "标记约定：<del>删除线</del> = 被改掉/删掉的原文；<ins>下划线</ins> = 改后的新文字；"
        "指标表 ↓/↑ = 相对人类参考的改善/恶化。",
        "",
        "## 一、指标前后对比",
        "",
        metric_table_md(d0, d1),
    ]
    sem_md = semantic_section_md(sem)
    if sem_md:
        parts.append(sem_md)
    parts.extend([
        "## 二、分级问题清单（改前检测）",
        "",
        findings_section_md(d0),
        "C 级（结构/节奏）见指标表；F 指纹见表内指纹行；"
        "比喻贴切度只能人审；本轮默认保留。用户主动要求时再列出相关原句供判断。",
        "",
        "## 三、前后对照（改后稿全文，改动处标记）",
        "",
        diff_section_md(t0, t1),
    ])
    return "\n\n".join(parts)


# ---------------- 组装 ----------------

def build_report(t0, t1, d0, d1, sem, name0, name1):
    parts = [
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">",
        f"<title>去AI味报告 · {esc(name0)}</title><style>{CSS}</style></head><body>",
        f"<h1>去AI味 · 前后对比报告</h1>",
        f'<p class="small">{esc(name0)} → {esc(name1)}</p>',
        '<div class="legend">图例：<span class="chg">红色</span> = 改后的新文字；'
        '<span class="del">灰色删除线</span> = 被改掉/删掉的原文；'
        '指标表 ↓/↑ = 相对人类参考的改善/恶化。</div>',
        "<h2>一、指标前后对比</h2>",
        metric_table(d0, d1),
        semantic_section(sem),
        "<h2>二、分级问题清单（改前检测）</h2>",
        findings_section(d0),
        '<p class="small">C 级（结构/节奏）见指标表；F 指纹见表内指纹行；'
        "比喻贴切度只能人审；本轮默认保留。用户主动要求时再列出相关原句供判断。</p>",
        "<h2>三、标红前后对照</h2>",
        diff_section(t0, t1),
        "</body></html>",
    ]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before", help="改前文本文件")
    ap.add_argument("after", help="改后文本文件")
    ap.add_argument("json_before", help="改前 detect --json 输出")
    ap.add_argument("json_after", help="改后 detect --json 输出")
    ap.add_argument("--semantic", help="语义判读结果 JSON（候选+label 字段）")
    ap.add_argument("--format", choices=["md", "html"], default="md",
                    help="报告格式：md=Markdown（默认，与文稿同格式可复制），html=单文件网页")
    ap.add_argument("--out", default=None,
                    help="输出路径；默认按格式取名 去AI味报告.md / .html")
    args = ap.parse_args()

    t0 = Path(args.before).read_text(encoding="utf-8", errors="ignore")
    t1 = Path(args.after).read_text(encoding="utf-8", errors="ignore")
    d0 = json.loads(Path(args.json_before).read_text(encoding="utf-8"))
    d1 = json.loads(Path(args.json_after).read_text(encoding="utf-8"))
    sem = None
    if args.semantic:
        sem = json.loads(Path(args.semantic).read_text(encoding="utf-8"))

    out = args.out or f"去AI味报告.{args.format}"
    if args.format == "md":
        page = build_report_md(t0, t1, d0, d1, sem, args.before, args.after)
    else:
        page = build_report(t0, t1, d0, d1, sem, args.before, args.after)
    Path(out).write_text(page, encoding="utf-8")
    n_han = lambda t: len(re.findall(r"[一-鿿]", t))
    print(f"报告 → {out}（改前 {n_han(t0)} 字 / 改后 {n_han(t1)} 字，"
          f"变化 {n_han(t1) - n_han(t0):+d}）")


if __name__ == "__main__":
    main()
