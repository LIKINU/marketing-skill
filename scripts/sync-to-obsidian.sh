#!/usr/bin/env bash
# ==========================================================================
# sync-to-obsidian.sh —— 把本 skill 同步到 Obsidian 離線存檔
#
# 用途：每次 `git push` 到 GitHub 時**自動**執行（由 .git/hooks/pre-push 觸發），
#       也可隨時手動執行。
# 用法：bash scripts/sync-to-obsidian.sh
#       （在 marketing-playbook/ 目錄下）
#
# 設計說明：
#   - 用 rsync **鏡像同步**（--delete）：源刪掉的文件，存檔裡也刪掉，保持一致
#   - 排除 .git / .DS_Store（存檔不需要版本歷史）
#   - 每次同步後**重新生成存檔說明.md**，寫入當前 commit 與同步時間
#   - 有安全檢查：目標路徑必須在 Obsidian 筆記庫內，否則中止（防 --delete 誤刪）
# ==========================================================================
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/Desktop/Obsidian笔记库/40-Archive/營銷skill-marketing-playbook-離線存檔"

# ---------- 安全檢查（防 --delete 誤刪）----------
if [[ "$DEST" != *"Obsidian笔记库"* ]]; then
    echo "❌ 目標路徑異常，中止：$DEST" >&2
    exit 1
fi
if [[ ! -d "$(dirname "$DEST")" ]]; then
    echo "❌ 上層目錄不存在，中止：$(dirname "$DEST")" >&2
    exit 1
fi
# 2026-09-16 改：不再綁定資料夾名（內容已平鋪到倉庫根），改用「這是不是 skill 根目錄」判斷
if [[ ! -f "$SRC/SKILL.md" || ! -d "$SRC/references" ]]; then
    echo "❌ 來源路徑異常（找不到 SKILL.md／references），中止：$SRC" >&2
    exit 1
fi

mkdir -p "$DEST"

# ---------- 同步 ----------
rsync -a --delete \
    --exclude '.git' \
    --exclude '.DS_Store' \
    --exclude '.workbuddy' \
    --exclude '实测-*' \
    "$SRC/" "$DEST/"

# ---------- 取真實數字（一律現算，不手寫）----------
# 2026-09-18：原本這些數字是手寫死在下面的說明模板裡的，結果全部過期了
#   （寫「104 條打法」而實際 116、「628 張案例卡」早已作廢、「08 號」質量範式
#   早就改成 07 號、「八條強制協議」實際七條）。手寫的數字一定會過期 —— 現算。
STATS="$(cd "$SRC" && python3 - <<'PY' 2>/dev/null || echo "?|?|?|?|?|?"
import glob, sys
sys.path.insert(0, "scripts")
try:
    import composer
    n_play = len(composer.parse_playbook(open("references/00-打法库.md", encoding="utf-8").read()))
    composer.load_model_names("references/03-方法论操作手册.md")
    n_model = len(composer._M03_RE)
except Exception:
    n_play = n_model = "?"
n_case = len(glob.glob("references/cases/[0-9][0-9]-*.md"))
n_ref = len(glob.glob("references/[0-9][0-9]-*.md"))
n_script = len(glob.glob("scripts/*.py")) + len(glob.glob("scripts/*.sh"))
qf = [f for f in glob.glob("references/*质量范式*") if f.endswith(".md")]
print(f"{n_play}|{n_model}|{n_case}|{n_ref}|{n_script}|{qf[0] if qf else '?'}")
PY
)"
IFS='|' read -r N_PLAY N_MODEL N_CASE N_REF N_SCRIPT QF_PATH <<<"$STATS"

# ---------- 重新生成存檔說明（含當前 commit 與時間）----------
SHA="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BRANCH="$(git -C "$SRC" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')"
NOW="$(date '+%Y-%m-%d %H:%M')"
FILES="$(find "$DEST" -type f -not -name '存檔說明.md' | wc -l | tr -d ' ')"
SIZE="$(du -sh "$DEST" 2>/dev/null | cut -f1)"

cat > "$DEST/存檔說明.md" <<EOF
# 營銷 Skill 離線存檔說明

> ⚙️ **本存檔由 \`scripts/sync-to-obsidian.sh\` 自動同步** —— 無需手動維護。
> **最後同步**：$NOW ｜ **版本**：\`$SHA\`（分支 ${BRANCH}）｜ **規模**：$FILES 個檔案 / $SIZE

**在線倉庫**：https://github.com/LIKINU/marketing-skill
**本地工作區**：\`$HOME/Desktop/Marketing-skill/\`

---

## 同步機制（重要）

每次在本地工作區執行 \`git push\` 時，\`.git/hooks/pre-push\` 會自動呼叫
\`scripts/sync-to-obsidian.sh\`，把 skill 的**最新內容鏡像到本目錄**。

- **觸發時機**：git push 前（pre-push hook）
- **同步方式**：rsync 鏡像（源刪掉的文件，這裡也刪掉）
- **手動同步**：\`cd ~/Desktop/Marketing-skill && bash scripts/sync-to-obsidian.sh\`
- **排除項**：\`.git\`（版本歷史）、\`.DS_Store\`

## 內容

| 路徑 | 內容 |
|---|---|
| \`SKILL.md\` | **主入口**：門禁 13 項 ＋ 七條強制執行協議 ＋ 六步工作流 ＋ 交付物規範 ＋ 自檢清單 |
| \`AGENTS.md\` | 跨工具接入手册（GPT／Claude Code／豆包等平台的降級方案） |
| \`README.md\` | 使用說明 ＋ 倉庫地圖 ＋「卡死了怎麼辦」 |
| \`references/\` | **$N_REF 份編號文檔**：打法庫 **$N_PLAY 條**／方法論手冊 **$N_MODEL 個模型**／**$N_CASE 大類案例庫**／「$QF_PATH」（質量標尺）／跨工具與操作 SOP／頂級機構對標標準 |
| \`scripts/\` | **$N_SCRIPT 支腳本**（強制層，校驗不過拿不到 \`.docx\`）：**\`flow.py\`（流程嚮導）／\`composer.py\`（方案組裝器，知識機械注入）／\`run_pipeline.py\`（唯一出稿入口）／\`selfcheck.py\`（18 關自檢）／\`kb_audit.py\`（知識庫連通性審計）／\`verify_all.py\`（全鏈路＋冪等壓測）** 等 |

## 怎麼查

| 想要 | 去哪 |
|---|---|
| **怎麼用**（接案 SOP ＋ 生成器規範摘要） | C 層 [[营销接案工具箱]] 第七節「方案生成器用法」 |
| **規範細節** | 本存檔 \`SKILL.md\` |
| **質量標準** | 本存檔 \`$QF_PATH\`（角色產出規格／骨架模板／可校驗指標） |
| **具體案例** | 本存檔 \`references/cases/\`（$N_CASE 個大類）｜**成品樣張**：\`references/范例/\` |
| **跨平台怎麼跑** | 本存檔 \`AGENTS.md\` |

## 已知限制

- 腳本需要 Python 3 ＋ \`python-docx\` 才能執行（本存檔只備份代碼，不含執行環境）
- 本存檔**不含** \`.git\` 歷史 —— 要版本歷史請看 GitHub
- ⚠️ 本目錄含多個 \`.md\`，Obsidian 會索引它們；若搜索時覺得重複，可在
  「設定 → 檔案與連結 → 排除的檔案」把本目錄加入
EOF

echo "✅ 已同步到 Obsidian 離線存檔"
echo "   目標：$DEST"
echo "   版本：$SHA ｜ 檔案：$FILES 個 ｜ 大小：$SIZE"
