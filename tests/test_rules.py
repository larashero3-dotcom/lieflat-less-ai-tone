"""规则算子的回归测试：六次测量失误的固化用例 + 各规则的正反例。

运行：
    python3 -m unittest discover -s tests
或：
    python3 tests/test_rules.py

操作规程（README 2.6）：改正则前先抽样看 20 条命中。本文件把规程落到机器上：
每个算子至少一条正例（必须命中）加一条反例（必须不命中），反例优先取自
README/RESEARCH 记录的真实失误材料。断言的是算子的行为边界，不是语言真相。
标注「已知落差」的用例固定的是算子与规则文字表述之间的覆盖差距：
修正算子时应同步更新断言，并按 2.6 规程重测语料。
"""
import importlib.util
import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_mod(name):
    # 脚本文件名带连字符，不能按模块名导入，只能按路径加载
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


compare = load_mod("compare-human-ai")
translationese = load_mod("check-translationese")
structure = load_mod("check-structure")

# (规则名, 文本, 是否期望命中, 依据)
COMPARE_CASES = [
    ("1 翻案腔", "真正的壁垒不是技术，而是认知。", True, "SKILL 第 1 条示例"),
    ("1 翻案腔", "这不是一个工具的问题，而是一个思维方式的问题。", True, "SKILL 第 1 条示例"),
    ("1 翻案腔", "真正的壁垒是认知。", False, "去掉翻案动作后不得命中"),

    ("2 顿号罗列过密", "平台覆盖采集、存储、展示三个环节。", True, "SKILL 第 2 条示例"),
    ("2 顿号罗列过密", "从采集到展示全流程已打通。", False, ""),
    ("2 顿号罗列过密", "支持按量、包月两种模式。", False, "两项并列不构成罗列过密"),

    ("4 破折号", "答案其实很简单——专注。", True, "SKILL 第 4 条示例"),
    ("4 破折号", "答案是专注。", False, ""),
    ("4 破折号", "取值范围写在 1—10 之间。", False, "单个连接号不是破折号"),

    ("5 冒号-提示语", "一句话总结：这个方案成本太高。", True, "SKILL 第 5 条示例"),
    ("5 冒号-提示语", "核心是：先解决支付失败的问题。", True, ""),
    ("5 冒号-提示语", "他说：明天再谈。", False, "引语式冒号明确豁免，失误记录 4"),
    ("5 冒号-提示语", "团队的核心是快速迭代。", False, ""),

    ("6 序数词当小标题", "首先，检查环境变量。\n其次，确认端口。", True, "行首序数词"),
    ("6 序数词当小标题", "## 一、先别急着写 prompt", False, "已知落差：算子只认词表，不覆盖「一、」式编号"),

    ("7 拟人化喻体", "它就像一位智慧的导师，不仅传授结论，更传授看待世界的多元视角。", True, "SKILL 第 7 条示例"),
    ("7 拟人化喻体", "这相当于为团队配备了一个永不疲倦、秒级响应的初级审查员。", True, ""),
    ("7 拟人化喻体", "它像一个老师傅，一眼看出问题所在。", False, "具体的人当喻体，是人类写法"),
    ("7 拟人化喻体", "这相当于一个临时的解决方案。", False, "无职业角色"),

    ("8 动词名词化", "团队完成了对系统稳定性的优化。", True, "SKILL 第 8 条附带处理的名词化结构"),
    ("8 动词名词化", "团队优化了系统稳定性。", False, ""),

    ("9 起手式", "说白了，这个项目没有足够的预算。", True, "SKILL 第 9 条示例"),
    ("9 起手式", "先说结论，这个方案不可行。", True, ""),
    ("9 起手式", "先把这个规则讲明白，再动手改。", False, ""),

    ("10 过长前置定语", "这是一个能够让团队在不增加人力的情况下显著提升审核速度的工具。", True, "SKILL 第 10 条示例"),
    ("10 过长前置定语", "质量管理是从0到1阶段最容易被忽视的问题。", False, "失误记录 1：普通句式不得算长定语"),

    ("10 当…时", "当所有人都能用 AI 写文章时，内容本身就不再是竞争优势。", True, "SKILL 第 10 条示例"),
    ("10 当…时", "当他回到家的时候，饭已经凉了。", False, "「的时候」是口语说法，明确豁免"),

    ("10 前置话题壳", "对于早期团队来说，招人是最难的事。", True, "SKILL 第 10 条示例"),
    ("10 前置话题壳", "关于定价，我们做了三轮测试。", True, "SKILL 词表含「关于」，此前脚本漏列"),
    ("10 前置话题壳", "一本关于定价的书出版了。", False, "「关于」不在句首收壳位置"),

    ("10 句首连接词", "然而，这个方案并不适用于所有场景。", True, "SKILL 第 10 条示例"),
    ("10 句首连接词", "风险可控，然而收益有限。", False, "连接词在句中不在行首"),

    ("10 这意味着", "留存率涨到了 72%。这意味着产品找到了 PMF。", True, "SKILL 第 10 条示例"),
    ("10 这意味着", "留存率涨到了 72%，产品找到了 PMF。", False, ""),
]

# 同一算子在两脚本重复定义是历史遗留；对译腔脚本的用例同时起互查作用
TRANSLATIONESE_CASES = [
    ("的…的…的连用", "需符合巴西的LGPD、印度的DPDPA、日本的APPI。", False, "失误记录 3：正常并立不得算嵌套定语"),
    ("的…的…的连用", "这是对系统架构的稳定性的影响的评估。", True, "真嵌套定语，共三个「的」"),
    ("并列连词密集", "方案更快，而且改动为零。", False, "失误记录 2：单次出现不算密集"),
    ("并列连词密集", "方案更快，而且更稳，并且迁移成本为零。", True, "单句内两次以上"),
    ("前置话题壳", "关于定价，我们做了三轮测试。", True, "与 compare-human-ai.py 词表保持一致"),
]


class TestSentenceOperators(unittest.TestCase):
    def test_compare_rules(self):
        for key, text, expect, why in COMPARE_CASES:
            with self.subTest(rule=key, text=text[:18]):
                rx = re.compile(compare.RULES[key])
                self.assertEqual(bool(rx.search(text)), expect, why)

    def test_translationese_markers(self):
        for key, text, expect, why in TRANSLATIONESE_CASES:
            with self.subTest(marker=key, text=text[:18]):
                rx = re.compile(translationese.MARKERS[key])
                self.assertEqual(bool(rx.search(text)), expect, why)

    def test_measure_smoke(self):
        # 小语料过一遍完整测量流程，确认计数与分母不出异常
        hits, k, _ = compare.measure(["真正的壁垒不是技术，而是认知。答案是专注。"])
        self.assertGreater(k, 0)
        self.assertGreater(hits["1 翻案腔"][0], 0)
        self.assertEqual(hits["4 破折号"][1], 0)


class TestParagraphOperators(unittest.TestCase):
    def test_isomorphic_positive(self):
        para = "我们改进了调度逻辑，缩短了排队时间。我们优化了缓存策略，降低了内存占用。"
        self.assertGreaterEqual(structure.isomorphic(para, 2), 1, "相邻句同款应被识别")

    def test_isomorphic_negative(self):
        para = "功能上线后用户反馈很好。下一步优化什么，已经定了。排期在下周，资源也已到位，预算同步审批。"
        self.assertEqual(structure.isomorphic(para, 2), 0, "骨架不同的相邻句不得误报")

    def test_isomorphic_triple(self):
        para = "我们改进了调度逻辑，缩短了排队时间。我们优化了缓存策略，降低了内存占用。我们收紧了超时配置，减少了无效等待。"
        self.assertGreaterEqual(structure.isomorphic(para, 3), 1, "三连同款单列计数")

    def _zero_subject(self, para):
        # 复刻 check-structure.py 的判定：非首段，评论语开头，且无回指成分
        return bool(structure.COMMENT.match(para) and not structure.ANAPHOR.match(para))

    def test_zero_subject_comment_positive(self):
        self.assertTrue(self._zero_subject("听起来像一条功能描述，其实底下换掉了一样更根本的东西。"),
                        "SKILL 第 11 条示例")
        self.assertTrue(self._zero_subject("值得注意的是，配置数据本来就按归属分层放着。"))

    def test_zero_subject_comment_negative(self):
        self.assertFalse(self._zero_subject("这听起来像一条功能描述，其实底下换掉了一样更根本的东西。"),
                         "补了回指词「这」后不得再计")
        self.assertFalse(self._zero_subject("这一点值得注意，配置数据本来就按归属分层放着。"))


if __name__ == "__main__":
    unittest.main()
