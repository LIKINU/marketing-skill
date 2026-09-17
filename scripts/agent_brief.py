#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_brief.py — 生成 `AGENT-BRIEF.md`（**给 agent 的单文件快照**）

为什么要有它（用户 2026-09-17 指出）：
    「**让你调 agent 修改的时候，每结束一次对话，再让你用 Agent 的时候，
      又要重新再读一遍，一直重复。**」

    这是实话：每个 agent 都是**全新上下文**，于是我每派一个 agent，它就把仓库从头读一遍。
    R1–R6 派了十几个 agent ＝ 同一个仓库被重读十几遍。**这是纯浪费。**

它怎么解决：
    把「agent 需要知道的仓库现状」压成**一份文件**（`AGENT-BRIEF.md`，目标 ≤ 6000 字）：
      ① 这是什么 ＋ 现在多大（自动统计）
      ② 目录结构 ／ 脚本分工 ／ 18 关自检（自动抽取）
      ③ 硬约定与禁令（语言纪律／P0 四条款／六条血泪判据）
      ④ 已知坑（每条都带「怎么发现的」）
      ⑤ 当前优化轮次状态（自动读 优化轮次/ 最新一份）

    → 派 agent 时**只给它这一份** ＋ 1–2 个目标文件的**那一节**（不是整份）。
      需要核对证据时才打开原档，且**只打开对应那一段**。

    ⚠️ 本档由脚本生成并挂在 `verify_all` 的幂等压测里 —— 改架构忘了更新它，会被哈希漂移抓出来。
       **能生成的简报就不要手写。**

用法：
    python scripts/agent_brief.py            # 写入 AGENT-BRIEF.md
    python scripts/agent_brief.py --print    # 只印到 stdout
"""
import argparse
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REF = os.path.join(ROOT, "references")
OUT = os.path.join(ROOT, "AGENT-BRIEF.md")

sys.path.insert(0, HERE)
from _common import OK, NG, WARN, HINT   # noqa: E402

# ── 脚本分类（顺序＝阅读顺序；新脚本归到最接近的一组） ──
GROUPS = [
    ("① 接案", ["flow.py", "gate_check.py", "start_here.py"]),
    ("② 组装", ["composer.py", "build_paradigm.py", "paradigm_data.py"]),
    ("③ 校验", ["selfcheck.py", "budget_check.py", "depth_check.py", "role_check.py",
                "structure_fix.py", "docx_footnote.py", "delivery_check.py"]),
    ("④ 出稿", ["run_pipeline.py", "build_docx.py", "reformat_to_template.py"]),
    ("⑤ 质量保障", ["verify_all.py", "kb_audit.py", "promise_check.py", "optimize_scan.py",
                    "smoke_test.py", "t2s_data.py"]),
    ("⑥ 案例库维护", ["case_sections.py", "case_order.py", "case_lint.py", "case_upgrade.py",
                      "case_scan.py", "case_clean.py", "case_relabel.py", "case_digest.py",
                      "case_gap_fill.py", "case_play_index.py", "fix_play_cases.py",
                      "play_case_candidates.py", "backlog_cleanup.py"]),
    ("⑦ 仓库维护", ["lang_unify.py", "repo_hygiene.py", "file_meta.py", "rename_tidy.py",
                    "top_titles.py", "relocate_06.py"]),
    ("⑧ 共用", ["_common.py"]),
]

# ── 硬约定（手写常量：这些不是能自动推出来的） ──
CONVENTIONS = """
- **语言**：**全仓统一简体**（知识库／脚本／文档／交付物都是简体；2026-09-18 用户裁定）。
  两个例外必须保留繁体：`t2s_data.py` 的 `T2S_PAIRS`（繁体字表＝侦测判据）、`smoke_test.py` 的繁体负向夹具。
- **P0 四条款**（优先于一切默认结构）：① 用户给的结构 > skill 默认，标题逐字沿用
  ② 用户大纲要作为**可见章节**存在，不打散 ③ 「自检通过」≠「交付达成」，用户的验收项要另行核对
  ④ 形状类任务**先交一页目录**再写正文。
- **交付形态红线**：对外一律简体 `.docx`；内部过程文档（事实底稿／分工／裁决记录）**不得混进交付稿**。
- **出稿唯一入口**：`run_pipeline.py`。拿不到 `.docx` ＝ 没完成，绕不过。
"""

# ── 六条血泪判据（每一条都是踩过才知道的） ──
LESSONS = """
1. **新加的硬关，先问「这条要求对最轻的那一档也成立吗」** —— 已连续五次误伤
   `smoke_test` 的速览类标杆稿。完整版才强制的走 `_hard_if_full()`。
2. **检测器要能区分「代码在找这个字符串」与「代码要访问这个路径」** —— 否则会把自己的
   正则、占位符词表、文件名索引串当成真问题（「提到 ≠ 读取」「引用 ≠ 消费」）。
3. **拿真稿调参，不要拿想像调参** —— 「为什么这么做」的判据初版误伤了机制句，
   补了条件推演／对照取舍／推理链三类句式才准。
4. **`except: pass` 一律不许** —— 最危险的一处：`verify_all` 哈希读不到档就跳过，
   于是「档怎么变都测不出漂移」，而报告照样印「零漂移」。
5. **脚本查了 ≠ 骨架给了位** —— 检查要求「表＋若干列」而骨架只给 `【填】`，检查必然空转。
   三环必须齐：**文档承诺 → 脚本检查 → 骨架给位**。
6. **口径只能在同层比较** —— 「月/年混用」检查做成整份文档范围，把分列清楚的标杆稿误判了；
   改成按**表块**判断才对。
7. **章节编号必须与实际出现顺序同向** —— 插了新节不改编号，一致性校验器会连续报「顺序不一致」。
8. **能生成的文档就不要手写** —— README 的结构表、这份 BRIEF，都挂在幂等压测里自动重生成；
   手写的必然过时。
"""


def read(p):
    try:
        return io.open(p, encoding="utf-8").read()
    except Exception:
        return ""


def nchars(s):
    return len(re.sub(r"\s", "", s))


def human(n):
    return f"{n/10000:.1f}万字" if n >= 10000 else f"{n}字"


def scan_checks():
    """从 selfcheck.py 抽出关号与标题（自动，不手写）。"""
    t = read(os.path.join(HERE, "selfcheck.py"))
    out = []
    for m in re.finditer(r'print\("\\n(【[0-9a-z]{1,3}】[^"]{0,60})', t):
        out.append(m.group(1).strip())
    seen, uniq = set(), []
    for x in out:
        k = x[:5]
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def latest_round():
    fs = sorted(glob.glob(os.path.join(ROOT, "优化轮次", "R*-20条.md")))
    if not fs:
        return "（暂无）"
    return os.path.basename(fs[-1]).replace(".md", "")


def build():
    py = sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
    cli = [f for f in py if '__name__ == "__main__"' in read(os.path.join(HERE, f))]
    refs = sorted(glob.glob(os.path.join(REF, "*.md")))
    cases = sorted(glob.glob(os.path.join(REF, "cases", "*.md")))
    total_ref = sum(nchars(f) for f in refs) + sum(nchars(f) for f in cases)
    L = []
    L.append("# AGENT-BRIEF · 给 agent 的单文件快照\n")
    L.append(f"> **为什么有这份**：每个 agent 都是全新上下文。没有这份，它会把整个仓库重读一遍 ——"
             f"派十几个 agent 就重读十几遍。\n"
             f"> **怎么用**：派 agent 时**只给这一份** ＋ **1–2 个目标档的「那一节」**；"
             f"需要核对证据时才打开原档，且**只开对应那一段，不要通读**。\n")
    L.append(f"> 本档由 `scripts/agent_brief.py` 生成并挂在 `verify_all` 的幂等压测里 —— "
             f"改架构忘了更新它会被哈希漂移抓出来。\n")

    L.append("\n## 一、这是什么（30 秒）\n")
    L.append("**营销方案生成器**：输入客户情况 → 输出一份可直接递给客户的 Word 营销方案"
             "（现状分析＋策划方案＋预算＋行动清单＋风险）。\n"
             "**核心设计**：知识由**脚本机械注入**骨架，模型只填 `【填】` —— **知识绕不过去**。\n"
             "**六档客户**：速览（小客户）／标准（C端品牌）／大赛／B端／G端／投标。\n")

    L.append("\n## 二、现在有多大（自动统计）\n")
    L.append(f"| 项 | 数量 | 体量 |\n|---|---|---|")
    L.append(f"| `references/` 编号文档 | {len(refs)} 份 | {human(sum(nchars(f) for f in refs))} |")
    L.append(f"| `references/cases/` 行业案例 | {len(cases)} 份 | {human(sum(nchars(f) for f in cases))} |")
    L.append(f"| `scripts/` | {len(py)} 支（{len(cli)} 支有 CLI） | — |")
    L.append(f"| 范式库 | 6 档 | 见 `references/12-范式库.md` |")
    L.append(f"| **合计** | — | **{human(total_ref)}** |")
    L.append(f"\n{HINT} **通读一遍＝烧掉大量上下文。用「查」代替「读」**："
             f"`python scripts/start_here.py --grep \"关键词\"`。\n")

    L.append("\n## 三、目录结构\n")
    L.append("```\nSKILL.md        唯一入口（§0 门禁 13 项 / §二路由表 / §六自检清单）\n"
             "AGENTS.md       跨工具接入说明 + 能力不足时怎么降级\n"
             "README.md       给人看的说明 + §零 仓库地图\n"
             "AGENT-BRIEF.md  ← 本档（给 agent 的快照）\n"
             "references/     知识库：00–13 编号文档 + cases/（52 行业）+ 范例/\n"
             "scripts/        强制层：知识注入 + 校验 + 出稿\n"
             "优化轮次/       过程记录（不是交付物）\n```\n")

    L.append("\n## 四、脚本分工（按「什么时候跑」）\n")
    for name, files in GROUPS:
        got = [f for f in files if f in py]
        if got:
            L.append(f"- **{name}**：`{'` · `'.join(got)}`")
    other = [f for f in py if not any(f in fs for _, fs in GROUPS)]
    if other:
        L.append(f"- **其他**：`{'` · `'.join(other)}`")

    ck = scan_checks()
    if ck:
        L.append(f"\n## 五、{len(ck)} 关机械自检（`selfcheck.py`，任一硬错误＝不得交付）\n")
        for x in ck:
            L.append(f"- {x}")

    L.append("\n## 六、硬约定（**不可违反**）\n")
    L.append(CONVENTIONS)

    L.append("\n## 七、已知坑（每一条都是踩过才知道的，别再踩）\n")
    L.append(LESSONS)

    L.append("\n## 八、当前状态\n")
    L.append(f"- 最新优化轮次：**{latest_round()}**（清单见 `优化轮次/`，含未做项与理由）\n"
             f"- 回归五条（改完任何东西都要跑）：\n"
             f"  ```bash\n"
             f"  python scripts/smoke_test.py          # 12 项冒烟（含标杆稿必须通过）\n"
             f"  python scripts/kb_audit.py            # L1–L7 断链必须全 0\n"
             f"  python scripts/promise_check.py       # 文档承诺 ↔ 实际执行\n"
             f"  python scripts/optimize_scan.py       # 机械可查的优化点\n"
             f"  python scripts/verify_all.py -n 50    # 全链路＋50 遍幂等（约 7 分钟）\n"
             f"  ```\n"
             f"- ⛔ **`verify_all` 运行期间绝对不要改仓库档** —— 它会把「运行中被改动」"
             f"如实报成哈希漂移，而你会以为脚本非幂等。\n")

    L.append("\n## 九、给 agent 的三条规矩\n")
    L.append("1. **只读本档 ＋ 1–2 个目标档的「那一节」**；需要证据时用 `grep` 定位行号，**不要通读整份文件**。\n"
             "2. **每个结论都要带证据**（档 ＋ 行号 ＋ 原文片段 ≤40 字）。不许写「文中多处」。\n"
             "3. **不许改任何文件**（除非常明确被要求）；凑不满条数就写「凑不满」。\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成 AGENT-BRIEF.md（给 agent 的单文件快照）")
    ap.add_argument("--print", action="store_true", help="只印到 stdout，不写档")
    a = ap.parse_args()
    txt = build()
    if a.print:
        print(txt)
    else:
        io.open(OUT, "w", encoding="utf-8").write(txt)
        print(f"{OK} 已生成 {os.path.relpath(OUT, ROOT)}（{human(nchars(txt))}）")
        print(f"{HINT} 已挂在 verify_all 的幂等压测里 —— 改架构会自动更新，不会漂。")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"{NG} agent_brief 执行出错：{type(e).__name__}: {e}")
        sys.exit(2)
