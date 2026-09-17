#!/usr/bin/env bash
# ==========================================================================
# sync-to-obsidian.sh —— 把本 skill 同步到 Obsidian 离线存档
#
# 用途：每次 `git push` 到 GitHub 时**自动**执行（由 .git/hooks/pre-push 触发），
#       也可随时手动执行。
# 用法：bash scripts/sync-to-obsidian.sh
#       （在 marketing-playbook/ 目录下）
#
# 设计说明：
#   - 用 rsync **镜像同步**（--delete）：源删掉的文件，存档里也删掉，保持一致
#   - 排除 .git / .DS_Store（存档不需要版本历史）
#   - 每次同步后**重新生成存档说明.md**，写入当前 commit 与同步时间
#   - 有安全检查：目标路径必须在 Obsidian 笔记库内，否则中止（防 --delete 误删）
# ==========================================================================
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/Desktop/Obsidian笔记库/40-Archive/营销skill-marketing-playbook-离线存档"

# ---------- 安全检查（防 --delete 误删）----------
if [[ "$DEST" != *"Obsidian笔记库"* ]]; then
    echo "❌ 目标路径异常，中止：$DEST" >&2
    exit 1
fi
if [[ ! -d "$(dirname "$DEST")" ]]; then
    echo "❌ 上层目录不存在，中止：$(dirname "$DEST")" >&2
    exit 1
fi
# 2026-09-16 改：不再绑定文件夹名（内容已平铺到仓库根），改用「这是不是 skill 根目录」判断
if [[ ! -f "$SRC/SKILL.md" || ! -d "$SRC/references" ]]; then
    echo "❌ 来源路径异常（找不到 SKILL.md／references），中止：$SRC" >&2
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

# ---------- 取真实数字（一律现算，不手写）----------
# 2026-09-18：原本这些数字是手写死在下面的说明模板里的，结果全部过期了
#   （写「104 条打法」而实际 116、「628 张案例卡」早已作废、「08 号」质量范式
#   早就改成 07 号、「八条强制协议」实际七条）。手写的数字一定会过期 —— 现算。
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
# 脚本数口径＝`scripts/*.py`（与 SKILL.md／README 一致）；`.sh` 另计，
# 2026-09-18 修：原先把 .py 与 .sh 加在一起报「46 支」，与 SKILL 的 45 对不上 —— 又是分母不一致。
n_script = len(glob.glob("scripts/*.py"))
n_sh = len(glob.glob("scripts/*.sh"))
qf = [f for f in glob.glob("references/*质量范式*") if f.endswith(".md")]
print(f"{n_play}|{n_model}|{n_case}|{n_ref}|{n_script}|{qf[0] if qf else '?'}|{n_sh}")
PY
)"
IFS='|' read -r N_PLAY N_MODEL N_CASE N_REF N_SCRIPT QF_PATH N_SH <<<"$STATS"
# ⚠️ 下面这些变量一律写 ${VAR} 带花括号：`$VAR` 后面若紧跟中文（如「$QF_PATH（质量标尺）」），
#    bash 会把多字节字符当成变量名的一部分 → `set -u` 直接报 unbound variable。
#    2026-09-18 实测踩过：`bash -n` 语法检查**通过**（它不求值展开），跑到一半才炸。

# ---------- 重新生成存档说明（含当前 commit 与时间）----------
SHA="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BRANCH="$(git -C "$SRC" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')"
NOW="$(date '+%Y-%m-%d %H:%M')"
FILES="$(find "$DEST" -type f -not -name '存档说明.md' | wc -l | tr -d ' ')"
SIZE="$(du -sh "$DEST" 2>/dev/null | cut -f1)"

# ⚠️ 下面这个 heredoc **没有加引号**（要展开 ${VAR}），所以在里面写 Markdown 反引号
#    **必须转义成 \`**：不转义会被 bash 当命令替换**真的去执行**。
#    2026-09-18 实测踩过：写成 `scripts/*.py` → 通配命中 scripts/_common.py → Permission denied。
#    `bash -n` 查不出来（语法合法）。
cat > "$DEST/存档说明.md" <<EOF
# 营销 Skill 离线存档说明

> ⚙️ **本存档由 \`scripts/sync-to-obsidian.sh\` 自动同步** —— 无需手动维护。
> **最后同步**：$NOW ｜ **版本**：\`$SHA\`（分支 ${BRANCH}）｜ **规模**：$FILES 个文件 / $SIZE

**在线仓库**：https://github.com/LIKINU/marketing-skill
**本地工作区**：\`$HOME/Desktop/Marketing-skill/\`

---

## 同步机制（重要）

每次在本地工作区执行 \`git push\` 时，\`.git/hooks/pre-push\` 会自动呼叫
\`scripts/sync-to-obsidian.sh\`，把 skill 的**最新内容镜像到本目录**。

- **触发时机**：git push 前（pre-push hook）
- **同步方式**：rsync 镜像（源删掉的文件，这里也删掉）
- **手动同步**：\`cd ~/Desktop/Marketing-skill && bash scripts/sync-to-obsidian.sh\`
- **排除项**：\`.git\`（版本历史）、\`.DS_Store\`

## 内容

| 路径 | 内容 |
|---|---|
| \`SKILL.md\` | **主入口**：门禁 13 项 ＋ 七条强制执行协议 ＋ 六步工作流 ＋ 交付物规范 ＋ 自检清单 |
| \`AGENTS.md\` | 跨工具接入手册（GPT／Claude Code／豆包等平台的降级方案） |
| \`README.md\` | 使用说明 ＋ 仓库地图 ＋「卡死了怎么办」 |
| \`references/\` | **${N_REF} 份编号文档**：打法库 **${N_PLAY} 条**／方法论手册 **${N_MODEL} 个模型**／**${N_CASE} 大类案例库**／「${QF_PATH}」（质量标尺）／跨工具与操作 SOP／顶级机构对标标准 |
| \`scripts/\` | **${N_SCRIPT} 支 Python 脚本 ＋ ${N_SH} 支同步脚本**（强制层，校验不过拿不到 \`.docx\`）：**\`flow.py\`（流程向导）／\`composer.py\`（方案组装器，知识机械注入）／\`run_pipeline.py\`（唯一出稿入口）／\`selfcheck.py\`（18 关自检）／\`kb_audit.py\`（知识库连通性审计）／\`verify_all.py\`（全链路＋幂等压测）** 等 |

## 怎么查

| 想要 | 去哪 |
|---|---|
| **怎么用**（接案 SOP ＋ 生成器规范摘要） | C 层 [[营销接案工具箱]] 第七节「方案生成器用法」 |
| **规范细节** | 本存档 \`SKILL.md\` |
| **质量标准** | 本存档 \`${QF_PATH}\`（角色产出规格／骨架模板／可校验指标） |
| **具体案例** | 本存档 \`references/cases/\`（${N_CASE} 个大类）｜**成品样张**：\`references/范例/\` |
| **跨平台怎么跑** | 本存档 \`AGENTS.md\` |

## 已知限制

- 脚本需要 Python 3 ＋ \`python-docx\` 才能执行（本存档只备份代码，不含执行环境）
- 本存档**不含** \`.git\` 历史 —— 要版本历史请看 GitHub
- ⚠️ 本目录含多个 \`.md\`，Obsidian 会索引它们；若搜索时觉得重复，可在
  「设定 → 文件与链接 → 排除的文件」把本目录加入
EOF

echo "✅ 已同步到 Obsidian 离线存档"
echo "   目标：$DEST"
echo "   版本：$SHA ｜ 文件：$FILES 个 ｜ 大小：$SIZE"
