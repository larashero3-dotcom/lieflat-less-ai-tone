"""人类语料 vs AI 语料的规则命中率对比报告。

用法：
    python3 scripts/compare-human-ai.py --human <目录> [更多] --ai <目录> [更多]

为什么要这个脚本：SKILL.md 里的「区分力 ×N」都来自一批已不可用的旧测量，
且切句逻辑有缺陷。本脚本用统一的测量方式同时跑人类侧和 AI 侧，
让每条规则的倍率可复现。倍率 = 人类频率 / AI 频率（<1 表示 AI 用得更多）。
"""
import re
import sys
import collections
from pathlib import Path

# 每条对应 SKILL.md 的一条规则，正则尽量贴规则的触发标记
RULES = {
    "2 翻案腔": r"(?:不是|并非|不在于)[^，。！？\n]{1,20}[，]?(?:而是|而在于)",
    # 原正则禁空格与字母，漏掉「用哪个模型、Team Skill 开关、定时任务」这类并列
    "3 顿号罗列过密": r"[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}、[^，。！？；：、\n]{1,14}",
    # 句内同构排比已移出规则：实测人类用得不比 AI 少，保留测量供复查
    "(已删)句内同构-更X": r"更[一-鿿]{1,3}[、，][^，。\n]{0,8}更[一-鿿]{1,3}",
    "(已删)句内同构-同字两项": r"([一-鿿]{1,2})[^，。、\n]{2,12}[、，]\1[^，。、\n]{2,12}",
    # 问句相关的规则已从 SKILL.md 删除，此处不再统计。三轮测量结论都不稳定：
    #   问号总量 —— 人类看似多 2.5 倍，但由个别组贡献，组间不一致
    #   自问自答 —— 倍率 1.03，宽正则还会误抓「？这是另一个问题」这类新起句
    #   小标题问句 —— 每千字 32 倍，换成占小标题比例后 AI 2.7% / 人类最高 3.6%，无差异
    # 教训：涉及结构元素的指标，先确认分母可比。
    "4 破折号": r"——",
    # 只匹配提示语+冒号（引出总结/结论/原因/定义），不匹配对话、标题、列表和普通句中冒号
    "5 提示性冒号": (r"(?:一句话(?:总结|说|概括)|简单说|说白了|总结|小结|结论|核心(?:是|在于|观点)?"
                    r"|关键(?:是|在于)?|重点(?:是)?|原因(?:如下|有|在于)?|问题(?:是|在于)?"
                    r"|答案(?:是)?|本质(?:是|上)?|定义(?:是)?|具体(?:来说|如下|包括)?"
                    r"|举例(?:来说)?|换句话说|也就是说|我的(?:观点|判断|结论)|建议(?:是)?)[：:]"),
    "6 序数词当小标题": r"(?:^|\n)\s*(?:首先|其次|再次|最后|第一|第二|第三|一方面|另一方面)[，、]",
    "(已删)就字": r"就",
    "(已删)很字": r"很",
    "(已删)了字": r"了",
    "(已删)口语连接词": r"但是|其实|不过|就是",
    "9 动词名词化": r"(?:完成|实现|进行|开展)了?(?:对)?[^，。\n]{0,10}的(?:优化|提升|调整|分析|改造|升级)",
    "11 过长前置定语": r"(?:一个|一种|一套|这种|这个)[^，。、；：！？\n]{15,}的[一-鿿]{2,5}",
    "11 当…时": r"当[^，。\n]{2,20}(?<!的时候)时，",
    "11 前置话题壳": r"(?:对于[^，。\n]{2,15}来说|对[^，。\n]{2,15}而言|就[^，。\n]{2,15}而言|在[^，。\n]{2,12}方面)",
    "11 句首连接词": r"(?:^|\n)\s*(?:然而|因此|此外|与此同时|换言之|总而言之)[，、]",
    "11 这意味着": r"(?:这意味着|这表明|这说明|换句话说)",
}


def load(dirs):
    out = []
    for d in dirs:
        for f in Path(d).rglob("*.md"):
            if f.parent.name == "_meta":
                continue
            try:
                out.append(f.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                continue
    return out


def measure(texts):
    joined = "\n".join(texts)
    k = len(re.findall(r"[一-鿿]", joined)) / 1000
    hits = {}
    for name, pat in RULES.items():
        rx = re.compile(pat)
        n = len(rx.findall(joined))
        docs = sum(1 for t in texts if rx.search(t))
        hits[name] = (n / k if k else 0, n, docs)
    return hits, k, len(texts)


def parse_args(argv):
    human, ai, cur = [], [], None
    for a in argv:
        if a == "--human":
            cur = human
        elif a == "--ai":
            cur = ai
        elif cur is not None:
            cur.append(a)
    return human, ai


def main():
    hd, ad = parse_args(sys.argv[1:])
    if not hd or not ad:
        print(__doc__)
        return

    # 每个人类目录单独测，用于判断差异在语料内部是否稳定（不输出各组明细）
    per_author = {}
    for d in hd:
        texts = load([d])
        if texts:
            # 不拿目录名当标签，也不输出各组数值：语料目录常带来源信息，
            # 逐组列出等于公开语料构成。只用来算稳定性。
            per_author[f"g{len(per_author) + 1}"] = measure(texts)
    ha = load(ad)
    if not per_author or not ha:
        print(f"语料为空：human={len(per_author)} 组, ai={len(ha)} 篇")
        return

    all_human = [t for d in hd for t in load([d])]
    hh, hk, hn = measure(all_human)
    ah, ak, an = measure(ha)

    names = list(per_author)
    print(f"人类语料：{hn} 篇，{hk/10:.1f} 万汉字")
    print(f"AI 语料：{an} 篇，{ak/10:.1f} 万汉字\n")

    head = f"{'规则':<18}{'人类':>8}{'AI':>7}{'倍率':>8}{'稳定性':>8}  判读"
    print(head)
    print("-" * (len(head) + 6))

    rows = []
    for name in RULES:
        h, a = hh[name][0], ah[name][0]
        ratio = h / a if a > 0.001 else float("inf")
        rows.append((ratio, name, h, a))

    for ratio, name, h, a in sorted(rows, key=lambda r: r[0]):
        disp = f"{ratio:>7.2f}" if ratio != float("inf") else "      ∞"
        # 各组数值只用来算稳定性，不打印——逐组列出等于公开语料构成
        vals = [per_author[n][0][name][0] for n in names]
        spread = max(vals) / max(min(vals), 0.01)
        stable = "稳定" if spread <= 5 else "波动大"
        if ratio < 0.5:
            verdict = "AI 明显更多 → 值得改"
        elif ratio < 0.8:
            verdict = "AI 略多"
        elif ratio <= 1.25:
            verdict = "无差异 → 不该作为规则"
        elif ratio <= 3:
            verdict = "人类更多"
        else:
            verdict = "人类明显更多 → 方向是补"
        if spread > 5 and ratio > 1.25:
            verdict += "（语料内部差异大，疑体裁）"
        print(f"{name:<18}{h:>8.2f}{a:>7.2f}{disp}{stable:>8}  {verdict}")


if __name__ == "__main__":
    main()
