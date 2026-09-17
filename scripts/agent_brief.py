#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_brief.py — 生成 `AGENT-BRIEF.md`（**给 agent 的单文件快照**）

為什麼要有它（用戶 2026-09-17 指出）：
    「**讓你調 agent 修改的時候，每結束一次對話，再讓你用 Agent 的時候，
      又要重新再讀一遍，一直重複。**」

    這是實話：每個 agent 都是**全新上下文**，於是我每派一個 agent，它就把倉庫從頭讀一遍。
    R1–R6 派了十幾個 agent ＝ 同一個倉庫被重讀十幾遍。**這是純浪費。**

它怎麼解決：
    把「agent 需要知道的倉庫現狀」壓成**一份檔**（`AGENT-BRIEF.md`，目標 ≤ 6000 字）：
      ① 這是什麼 ＋ 現在多大（自動統計）
      ② 目錄結構 ／ 腳本分工 ／ 18 關自檢（自動抽取）
      ③ 硬約定與禁令（語言紀律／P0 四條款／六條血淚判據）
      ④ 已知坑（每條都帶「怎麼發現的」）
      ⑤ 當前優化輪次狀態（自動讀 优化轮次/ 最新一份）

    → 派 agent 時**只給它這一份** ＋ 1–2 個目標文件的**那一節**（不是整份）。
      需要核對證據時才打開原檔，且**只打開對應那一段**。

    ⚠️ 本檔由腳本生成並掛在 `verify_all` 的冪等壓測裡 —— 改架構忘了更新它，會被哈希漂移抓出來。
       **能生成的簡報就不要手寫。**

用法：
    python scripts/agent_brief.py            # 寫入 AGENT-BRIEF.md
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

# ── 腳本分類（順序＝閱讀順序；新腳本歸到最接近的一組） ──
GROUPS = [
    ("① 接案", ["flow.py", "gate_check.py", "start_here.py"]),
    ("② 組裝", ["composer.py", "build_paradigm.py", "paradigm_data.py"]),
    ("③ 校驗", ["selfcheck.py", "budget_check.py", "depth_check.py", "role_check.py",
                "structure_fix.py", "docx_footnote.py", "delivery_check.py"]),
    ("④ 出稿", ["run_pipeline.py", "build_docx.py", "reformat_to_template.py"]),
    ("⑤ 品質保障", ["verify_all.py", "kb_audit.py", "promise_check.py", "optimize_scan.py",
                    "smoke_test.py", "t2s_data.py"]),
    ("⑥ 案例庫維護", ["case_sections.py", "case_order.py", "case_lint.py", "case_upgrade.py",
                      "case_scan.py", "case_clean.py", "case_relabel.py", "case_digest.py",
                      "case_gap_fill.py", "case_play_index.py", "fix_play_cases.py",
                      "play_case_candidates.py", "backlog_cleanup.py"]),
    ("⑦ 倉庫維護", ["file_meta.py", "rename_tidy.py", "top_titles.py", "relocate_06.py"]),
    ("⑧ 共用", ["_common.py"]),
]

# ── 硬約定（手寫常量：這些不是能自動推出來的） ──
CONVENTIONS = """
- **語言**：交付物一律**簡體**；skill 內部文檔一律**繁體**；`references/09–13` 例外（簡體，因內容原樣進交付物）。
- **P0 四條款**（優先於一切默認結構）：① 用戶給的結構 > skill 默認，標題逐字沿用
  ② 用戶大綱要作為**可見章節**存在，不打散 ③ 「自檢通過」≠「交付達成」，用戶的驗收項要另行核對
  ④ 形狀類任務**先交一頁目錄**再寫正文。
- **交付形態紅線**：對外一律簡體 `.docx`；內部過程文檔（事實底稿／分工／裁決記錄）**不得混進交付稿**。
- **出稿唯一入口**：`run_pipeline.py`。拿不到 `.docx` ＝ 沒完成，繞不過。
"""

# ── 六條血淚判據（每一條都是踩過才知道的） ──
LESSONS = """
1. **新加的硬關，先問「這條要求對最輕的那一檔也成立嗎」** —— 已連續五次誤傷
   `smoke_test` 的速覽類標杆稿。完整版才強制的走 `_hard_if_full()`。
2. **檢測器要能區分「代碼在找這個字符串」與「代碼要訪問這個路徑」** —— 否則會把自己的
   正則、佔位符詞表、檔名索引串當成真問題（「提到 ≠ 讀取」「引用 ≠ 消費」）。
3. **拿真稿調參，不要拿想像調參** —— 「為什麼這麼做」的判據初版誤傷了機制句，
   補了條件推演／對照取捨／推理鏈三類句式才準。
4. **`except: pass` 一律不許** —— 最危險的一處：`verify_all` 哈希讀不到檔就跳過，
   於是「檔怎麼變都測不出漂移」，而報告照樣印「零漂移」。
5. **腳本查了 ≠ 骨架給了位** —— 檢查要求「表＋若干列」而骨架只給 `【填】`，檢查必然空轉。
   三環必須齊：**文檔承諾 → 腳本檢查 → 骨架給位**。
6. **口徑只能在同層比較** —— 「月/年混用」檢查做成整份文檔範圍，把分列清楚的標杆稿誤判了；
   改成按**表塊**判斷才對。
7. **章節編號必須與實際出現順序同向** —— 插了新節不改編號，一致性校驗器會連續報「順序不一致」。
8. **能生成的文檔就不要手寫** —— README 的結構表、這份 BRIEF，都掛在冪等壓測裡自動重生成；
   手寫的必然過時。
"""


def read(p):
    try:
        return io.open(p, encoding="utf-8").read()
    except Exception:
        return ""


def nchars(s):
    return len(re.sub(r"\s", "", s))


def human(n):
    return f"{n/10000:.1f}萬字" if n >= 10000 else f"{n}字"


def scan_checks():
    """從 selfcheck.py 抽出關號與標題（自動，不手寫）。"""
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
        return "（暫無）"
    return os.path.basename(fs[-1]).replace(".md", "")


def build():
    py = sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
    cli = [f for f in py if '__name__ == "__main__"' in read(os.path.join(HERE, f))]
    refs = sorted(glob.glob(os.path.join(REF, "*.md")))
    cases = sorted(glob.glob(os.path.join(REF, "cases", "*.md")))
    total_ref = sum(nchars(f) for f in refs) + sum(nchars(f) for f in cases)
    L = []
    L.append("# AGENT-BRIEF · 給 agent 的單檔快照\n")
    L.append(f"> **為什麼有這份**：每個 agent 都是全新上下文。沒有這份，它會把整個倉庫重讀一遍 ——"
             f"派十幾個 agent 就重讀十幾遍。\n"
             f"> **怎麼用**：派 agent 時**只給這一份** ＋ **1–2 個目標檔的「那一節」**；"
             f"需要核對證據時才打開原檔，且**只開對應那一段，不要通讀**。\n")
    L.append(f"> 本檔由 `scripts/agent_brief.py` 生成並掛在 `verify_all` 的冪等壓測裡 —— "
             f"改架構忘了更新它會被哈希漂移抓出來。\n")

    L.append("\n## 一、這是什麼（30 秒）\n")
    L.append("**營銷方案生成器**：輸入客戶情況 → 輸出一份可直接遞給客戶的 Word 營銷方案"
             "（現狀分析＋策劃方案＋預算＋行動清單＋風險）。\n"
             "**核心設計**：知識由**腳本機械注入**骨架，模型只填 `【填】` —— **知識繞不過去**。\n"
             "**六檔客戶**：速覽（小客戶）／标准（C端品牌）／大赛／B端／G端／投标。\n")

    L.append("\n## 二、現在有多大（自動統計）\n")
    L.append(f"| 項 | 數量 | 體量 |\n|---|---|---|")
    L.append(f"| `references/` 編號文檔 | {len(refs)} 份 | {human(sum(nchars(f) for f in refs))} |")
    L.append(f"| `references/cases/` 行業案例 | {len(cases)} 份 | {human(sum(nchars(f) for f in cases))} |")
    L.append(f"| `scripts/` | {len(py)} 支（{len(cli)} 支有 CLI） | — |")
    L.append(f"| 範式庫 | 6 檔 | 見 `references/12-范式库.md` |")
    L.append(f"| **合計** | — | **{human(total_ref)}** |")
    L.append(f"\n{HINT} **通讀一遍＝燒掉大量上下文。用「查」代替「讀」**："
             f"`python scripts/start_here.py --grep \"關鍵詞\"`。\n")

    L.append("\n## 三、目錄結構\n")
    L.append("```\nSKILL.md        唯一入口（§0 門禁 13 項 / §二路由表 / §六自檢清單）\n"
             "AGENTS.md       跨工具接入說明 + 能力不足時怎麼降級\n"
             "README.md       給人看的說明 + §零 倉庫地圖\n"
             "AGENT-BRIEF.md  ← 本檔（給 agent 的快照）\n"
             "references/     知識庫：00–13 編號文檔 + cases/（52 行業）+ 范例/\n"
             "scripts/        強制層：知識注入 + 校驗 + 出稿\n"
             "优化轮次/       過程記錄（不是交付物）\n```\n")

    L.append("\n## 四、腳本分工（按「什麼時候跑」）\n")
    for name, files in GROUPS:
        got = [f for f in files if f in py]
        if got:
            L.append(f"- **{name}**：`{'` · `'.join(got)}`")
    other = [f for f in py if not any(f in fs for _, fs in GROUPS)]
    if other:
        L.append(f"- **其他**：`{'` · `'.join(other)}`")

    ck = scan_checks()
    if ck:
        L.append(f"\n## 五、{len(ck)} 關機械自檢（`selfcheck.py`，任一硬錯誤＝不得交付）\n")
        for x in ck:
            L.append(f"- {x}")

    L.append("\n## 六、硬約定（**不可違反**）\n")
    L.append(CONVENTIONS)

    L.append("\n## 七、已知坑（每一條都是踩過才知道的，別再踩）\n")
    L.append(LESSONS)

    L.append("\n## 八、當前狀態\n")
    L.append(f"- 最新優化輪次：**{latest_round()}**（清單見 `优化轮次/`，含未做項與理由）\n"
             f"- 回歸五條（改完任何東西都要跑）：\n"
             f"  ```bash\n"
             f"  python scripts/smoke_test.py          # 12 項冒煙（含標杆稿必須通過）\n"
             f"  python scripts/kb_audit.py            # L1–L7 斷鏈必須全 0\n"
             f"  python scripts/promise_check.py       # 文檔承諾 ↔ 實際執行\n"
             f"  python scripts/optimize_scan.py       # 機械可查的優化點\n"
             f"  python scripts/verify_all.py -n 50    # 全鏈路＋50 遍冪等（約 7 分鐘）\n"
             f"  ```\n"
             f"- ⛔ **`verify_all` 運行期間絕對不要改倉庫檔** —— 它會把「運行中被改動」"
             f"如實報成哈希漂移，而你會以為腳本非冪等。\n")

    L.append("\n## 九、給 agent 的三條規矩\n")
    L.append("1. **只讀本檔 ＋ 1–2 個目標檔的「那一節」**；需要證據時用 `grep` 定位行號，**不要通讀整份檔**。\n"
             "2. **每個結論都要帶證據**（檔 ＋ 行號 ＋ 原文片段 ≤40 字）。不許寫「文中多處」。\n"
             "3. **不許改任何文件**（除非常明確被要求）；湊不滿條數就寫「湊不滿」。\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成 AGENT-BRIEF.md（給 agent 的單檔快照）")
    ap.add_argument("--print", action="store_true", help="只印到 stdout，不寫檔")
    a = ap.parse_args()
    txt = build()
    if a.print:
        print(txt)
    else:
        io.open(OUT, "w", encoding="utf-8").write(txt)
        print(f"{OK} 已生成 {os.path.relpath(OUT, ROOT)}（{human(nchars(txt))}）")
        print(f"{HINT} 已掛在 verify_all 的冪等壓測裡 —— 改架構會自動更新，不會漂。")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"{NG} agent_brief 執行出錯：{type(e).__name__}: {e}")
        sys.exit(2)
