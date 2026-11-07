"""统计翻译腔标记在 AI 语料中的出现频率（每千汉字）。

用法：
    python3 scripts/check-translationese.py <语料目录> [更多目录...]

人类语料若不在本机，只能给出 AI 侧绝对频率：
某标记在 AI 文本里都极少出现时，它不可能是 AI 味的判别特征。
BASELINE 是研究已确认有区分力的规则，用同一脚本同一语料测量，作为收录门槛。
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

MARKERS = {
    "被动-抽象": r"被(认为|视为|称为|设计为|应用于|赋予|看作)",
    "受到…的": r"受到[^，。]{0,12}的(关注|影响|重视|挑战)",
    "形式主语": r"(值得注意的是|有必要指出的是|可以说的是|需要指出的是)",
    "存在着/有着": r"(存在着|有着)",
    "当…的时候": r"当[^，。]{2,20}(的时候|时)，",
    "在…的过程中": r"在[^，。]{2,20}(的过程中|的情况下)",
    "如果…的话": r"如果[^，。]{2,20}的话",
    "并列连词密集": r"并且|而且",
    "轻动词": r"(进行|作出|给予|予以)了?[^，。]{0,6}(分析|调整|优化|支持|评估|检查|讨论)",
    "不仅仅是": r"(不仅仅是|远不止是|不过是|无非是)",
    "正是/恰恰是": r"(正是|恰恰是)",
    "复数硬译": r"(一系列的|各种各样的|诸多)",
    "程度直译": r"(在某种程度上|一定程度上|从某种意义上说|在很大程度上|相对而言)",
    "句首连接词": r"(?:^|\n)\s*(然而|因此|此外|与此同时|换言之|总而言之)[，、]",
    "这意味着": r"(这意味着|这表明|这说明|换句话说)",
    "前置话题壳": r"(对于[^，。]{2,15}来说|对[^，。]{2,15}而言|就[^，。]{2,15}而言|在[^，。]{2,12}方面)",
    "扮演角色": r"(扮演|承担)了?[^，。]{0,8}角色",
    "以一种…方式": r"以一种[^，。]{2,12}的(方式|形式)",
    "使得…能够": r"使得?[^，。]{0,12}(能够|可以)",
    "长前置定语": r"(?:一个|一种|一套|这种|这个)[^，。、；：！？\n]{15,}的[一-鿿]{2,5}",
    "的…的…的连用": r"的[^，。]{1,8}的[^，。]{1,8}的",
}

# 对照基准：研究已确认有区分力的规则，同一脚本同一语料
BASELINE = {
    "[基准]段首序数词": r"(?:^|\n)\s*(首先|其次|再次|最后|第一|第二|第三|一方面|另一方面)",
    "[基准]不是…而是": r"(不是|并非)[^，。]{1,20}(，|)而是",
    "[基准]破折号": r"——",
    # 只匹配提示语+冒号；宽正则（任意汉字+冒号）会把标题、列表、对话一并算进来
    "[基准]提示性冒号": (r"(?:一句话(?:总结|说|概括)|简单说|说白了|总结|小结|结论|核心(?:是|在于|观点)?"
                       r"|关键(?:是|在于)?|重点(?:是)?|原因(?:如下|有|在于)?|问题(?:是|在于)?"
                       r"|答案(?:是)?|本质(?:是|上)?|定义(?:是)?|具体(?:来说|如下|包括)?"
                       r"|举例(?:来说)?|换句话说|也就是说|我的(?:观点|判断|结论)|建议(?:是)?)[：:]"),
}


def model_of(path):
    return re.sub(r"-T\d.*", "", Path(path).stem)


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print(__doc__)
        return
    files = [f for d in dirs for f in Path(d).rglob("*.md") if f.parent.name != "_meta"]
    if not files:
        print(f"找不到语料：{dirs}")
        return

    texts = {f: f.read_text(encoding="utf-8") for f in files}
    joined = "\n".join(texts.values())
    kchars = len(re.findall(r"[一-鿿]", joined)) / 1000
    models = sorted({model_of(f) for f in files})
    print(f"语料 {len(files)} 篇，{kchars/10:.1f} 万汉字，模型 {len(models)} 个：{', '.join(models)}\n")

    # 每模型汉字数，用于分模型频率
    mk = defaultdict(float)
    for f, t in texts.items():
        mk[model_of(f)] += len(re.findall(r"[一-鿿]", t)) / 1000

    rows = []
    for name, pat in {**MARKERS, **BASELINE}.items():
        rx = re.compile(pat)
        total = len(rx.findall(joined))
        docs = sum(1 for t in texts.values() if rx.search(t))
        per_model = {m: len(rx.findall("\n".join(t for f, t in texts.items() if model_of(f) == m))) / mk[m]
                     for m in models}
        rows.append((total / kchars, total, docs, name, per_model))
    rows.sort(reverse=True)

    head = f"{'标记':<16}{'每千字':>8}{'总数':>7}{'覆盖':>10}  " + "".join(f"{m[:11]:>12}" for m in models)
    print(head)
    print("-" * len(head))
    for per_k, total, docs, name, pm in rows:
        cov = f"{docs}/{len(files)}"
        line = f"{name:<16}{per_k:>8.2f}{total:>7}{cov:>10}  " + "".join(f"{pm[m]:>12.2f}" for m in models)
        print(line)


if __name__ == "__main__":
    main()
