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
    "$SRC/" "$DEST/"

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
**本地工作區**：\`/Users/user/Desktop/Marketing-skill/\`

---

## 同步機制（重要）

每次在本地工作區執行 \`git push\` 時，\`.git/hooks/pre-push\` 會自動呼叫
\`scripts/sync-to-obsidian.sh\`，把 skill 的**最新內容鏡像到本目錄**。

- **觸發時機**：git push 前（pre-push hook）
- **同步方式**：rsync 鏡像（源刪掉的文件，這裡也刪掉）
- **手動同步**：\`cd /Users/user/Desktop/Marketing-skill && bash scripts/sync-to-obsidian.sh\`
- **排除項**：\`.git\`（版本歷史）、\`.DS_Store\`

## 內容

| 路徑 | 內容 |
|---|---|
| \`SKILL.md\` | **主入口**：門禁 13 項 ＋ 八條強制協議 ＋ 六步工作流 ＋ 交付物規範 ＋ 自檢清單 |
| \`AGENTS.md\` | 跨工具接入手册（GPT／Claude Code／豆包等平台的降級方案） |
| \`README.md\` | 使用說明 ＋ 三句兜底話術 ＋「卡死了怎麼辦」 |
| \`references/\` | 打法庫 104 條／方法論手冊 63 個模型／**50 大類 628 張案例卡**／方案寫作指南／多 Agent 分工簡報／**質量範式（08 號）**／**交付稿範例（簡體）** |
| \`scripts/\` | 5 個校驗腳本：\`gate_check\`／\`budget_check\`／\`selfcheck\`／\`depth_check\`／\`build_docx\` |

## 怎麼查

| 想要 | 去哪 |
|---|---|
| **怎麼用**（接案 SOP ＋ 生成器規範摘要） | C 層 [[营销接案工具箱]] 第七節「方案生成器用法」 |
| **規範細節** | 本存檔 \`SKILL.md\` |
| **質量標準** | 本存檔 \`references/08-质量范式-便利店开学季案.md\`（角色產出規格／骨架模板／可校驗指標） |
| **具體案例** | 本存檔 \`references/cases/\`（50 個大類）｜**成品樣張**：\`references/范例/\` |
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
