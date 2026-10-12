# china-mba-case-thesis-skill

中国高校 MBA（及管理类专业硕士）**单企业案例型学位论文**的写作辅助方法，做成了 AI 智能体可用的 skill：从对标范文、搭框架、向企业取证、分章成文、脚本生成 Word，到按导师意见迭代，并附一套配套脚本。

## 适合谁

- 正在用 Claude、ChatGPT 等 AI 助手写 MBA / 专业硕士论文的人：把这个 skill 给助手，它会按固定流程工作，而不是每次从零开始
- 想要一套"Markdown 写源稿 → 脚本生成合规 Word"流水线的人：`china-mba-case-thesis/scripts/` 可以单独用

## 使用边界

- 只针对**单企业案例型**的 MBA / 管理类专业硕士论文；定量实证、多案例比较、本科论文和期刊论文不在范围内
- 助手可以起草，但问题判断、原因归纳、方案取舍和最终文字由作者负责；不编造数据和参考文献
- 使用前请查清本校对 AI 辅助写作的规定，按规定使用和披露。本 skill 不提供“降 AIGC 率”或规避检测的改写

## 怎么用

skill 本体是 `china-mba-case-thesis/` 这个文件夹，安装时只复制它，仓库根目录的其他文件（README、evals 等）不用复制。先把仓库克隆下来，或者在 GitHub 页面点 Code → Download ZIP：

```bash
git clone https://github.com/shizzhang0/china-mba-case-thesis-skill.git
```

**Claude Code**：把 `china-mba-case-thesis/` 复制到 `~/.claude/skills/china-mba-case-thesis/`（全局；Windows 上是 `%USERPROFILE%\.claude\skills\china-mba-case-thesis\`）或项目下的 `.claude/skills/china-mba-case-thesis/`，之后提到"毕业论文 / MBA 论文 / 案例分析"时会自动触发，也可以用 `/china-mba-case-thesis` 调用。

**Claude.ai**：把 `china-mba-case-thesis/` 文件夹打成 zip，在 设置 → 功能 → Skills 里上传。

**其他智能体**：`SKILL.md` 是一份普通的 Markdown 说明书，直接作为系统提示或项目说明给它读即可；`references/` 在对应阶段再读。

**不用 AI 也能用**：`SKILL.md` + `references/` 本身就是一份写作指南，`scripts/` 的脚本不依赖 AI。

## 目录

```
README.md / LICENSE / CHANGELOG.md
evals/                  skill 的评测用例（不属于 skill 本体，安装时不用复制）
china-mba-case-thesis/  skill 本体
  SKILL.md              方法总纲：助手的角色与边界、六条原则、从哪里进入、每次开工先做的事、文件管理、六个阶段
  references/           各阶段细则：取证、访谈与问卷、成文、合稿与检查、整体审查清单、源稿约定、文件管理
  scripts/              配套脚本（见 scripts/README.md）
    snapshot.py           大改前打 zip 快照，代替复制加后缀
    survey/               范文横向统计（页数、章节、图表数、关键词频次）
    docx/                 Markdown 源稿 → 学位论文 Word（只用 Python 标准库），学校格式写在配置文件里
    figures/              示意图辅助库与数据图示例（matplotlib），全文统一风格
    check/                文本对比、PDF 版面抽查、目录文字与页码核对
  templates/            决定日志、章节源稿模板
  example/              虚构企业 YT 公司的示例源稿（含一章完整的现状与问题分析）和绘图脚本
```

## 快速试跑

只需要 Python 3.8 以上。生成 Word 不用装任何包：

```bash
cd china-mba-case-thesis/scripts/docx
```

```bash
python build_docx.py thesis.config.example.json 示例.docx
```

用 `example/` 的源稿生成一份 Word。目录条目已经按标题填好，页码要在 Word 里更新目录后保存才有。画图脚本另需 `pip install matplotlib`。其余脚本的依赖和平台说明见 `china-mba-case-thesis/scripts/README.md`。脚本在 Windows 11 上逐个实测过（`render_pdf.py` 除外，它需要 LibreOffice）。

## 方法的核心

1. 证据先于文字：每个判断都有依据，没有就留占位，不编造
2. 对标本地标准：导师推荐论文和本院范文是第一参照
3. 一条逻辑链贯穿全文：问题、原因、方案、效果一一对应，改一处全链联动
4. 过程外化：判断写成文件，不只留在对话里
5. 单一源稿，整份重建：只改 Markdown 和绘图脚本，Word 和图每次重新生成
6. 作者拍板，助手提方案：决定记入决定日志

## 评测

`evals/` 里有三类评测，所有用例都是虚构的，跑法和每轮结果见 [`evals/README.md`](evals/README.md)：

- **触发**：20 条提问（10 条应该用上本 skill，10 条相近但不应该用，如降 AIGC 率、定量实证、本科论文、教学案例），20 条全部判对
- **入口与边界**：7 条提问，看助手是否从作者所处的阶段切入，是否守住不编造、不帮助规避检测、范围之外如实说明
- **虚构案例**：餐饮（写一节正文）、物流（企业数据到手后的解读）、银行（送审前整体审查），附标准答案

最近一轮（入口与边界的 4 条 + 3 个案例），带 skill 通过 49/52 个检查点，不带 skill 通过 37/52。差别主要不在找问题、算数字这些模型本来就会的事，而在流程纪律：不带 skill 时，3 个案例里有 2 次未经作者确认就直接改了稿子，1 次自行选定了统计口径；带 skill 时都先写解读、只报不改，把需要拍板的事交给作者。

局限：评测由 AI 子代理执行和评分，每条只跑一到两次；触发测试用的是替代做法（让子代理从 skill 列表里选），只能说明 description 写得清楚，不等于真实环境里的触发率。

## 许可

MIT。方法和脚本都可以自由修改使用；用它写出来的论文当然是你自己的。

---

*A skill for AI agents: a method for drafting case-study MBA theses at Chinese universities, with scripts for Markdown-to-Word generation, figure drawing, sample-thesis statistics and TOC checking. Documentation is in Chinese, as is the thesis format it targets.*
