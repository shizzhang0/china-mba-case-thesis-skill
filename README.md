# china-mba-case-thesis-skill

中国高校 MBA（及管理类专业硕士）**单企业案例型学位论文**的写作辅助方法，做成了 AI 智能体可用的 skill：从对标范文、搭框架、向企业取证、分章成文、脚本生成 Word，到按导师意见迭代，并附一套配套脚本。

## 适合谁

- 正在用 AI 助手写 MBA / 专业硕士论文的人：把这个 skill 给助手，它会按固定流程工作，而不是每次从零开始

## 使用边界

- 只针对**单企业案例型**的 MBA / 管理类专业硕士论文；定量实证、多案例比较、本科论文和期刊论文不在范围内
- 助手可以起草，但问题判断、原因归纳、方案取舍和最终文字由作者负责；不编造数据和参考文献
- 使用前请查清本校对 AI 辅助写作的规定，按规定使用和披露。本 skill 不提供“降 AIGC 率”或规避检测的改写

## 怎么用

先看 [`START_HERE.md`](china-mba-case-thesis/START_HERE.md)：判断论文类型和当前任务，选标准或轻量路径。模板按需使用，不是入场清单。

skill 本体是 `china-mba-case-thesis/` 这个文件夹。下面两种方式任选一种，对能读文件的 AI 助手都适用。

**方式一：让 AI 直接读仓库。** 把这段话发给你的 AI 助手（它需要能打开网页链接）：

> 请阅读 https://raw.githubusercontent.com/shizzhang0/china-mba-case-thesis-skill/main/china-mba-case-thesis/SKILL.md ，按其中的方法协助我写论文。用到哪个阶段，再读它提到的 `references/`、`templates/` 里的文件，地址是把文件路径接在 https://raw.githubusercontent.com/shizzhang0/china-mba-case-thesis-skill/main/china-mba-case-thesis/ 后面。

这里给的是 raw 地址（纯文本），AI 读到的是原始 Markdown，不会把表格读乱。

**方式二：下载到本地。** 在本页点 Code → Download ZIP，或到 [Releases](https://github.com/shizzhang0/china-mba-case-thesis-skill/releases) 下载某个版本的源码包（Source code），解压后使用其中的 `china-mba-case-thesis/` 文件夹：

- 你的 AI 工具支持 skill（Agent Skills）的，把 `china-mba-case-thesis/` 文件夹放进它读取 skill 的目录，按工具的说明安装即可；
- 不支持的，直接告诉 AI：“读一下 `<解压路径>/china-mba-case-thesis/SKILL.md`，按它的方法帮我写论文。”

想用配套脚本（生成 Word、画图、范文统计等），AI 助手要能在你电脑上读写文件、运行命令，所以要用方式二。脚本只需要 Python 3.8 以上：生成 Word 不用装任何包，画图要 `pip install matplotlib`，详见 [`scripts/README.md`](china-mba-case-thesis/scripts/README.md)。

## 目录

```
README.md / LICENSE / CHANGELOG.md
china-mba-case-thesis/  skill 本体
  LICENSE.txt           许可（与根目录 LICENSE 相同，复制 skill 文件夹时随之带走）
  START_HERE.md         论文类型判断、轻量路径和按任务阅读入口
  SKILL.md              方法总纲：助手的角色与边界、六条原则、从哪里进入、每次开工先做的事、文件管理、六个阶段
  references/           各阶段细则：对标与搭框架、取证、访谈与问卷、成文、合稿与检查、整体审查清单、源稿约定、文件管理、负例与改写
  scripts/              配套脚本（见 scripts/README.md）
    snapshot.py           大改前打 zip 快照，代替复制加后缀
    survey/               范文横向统计（页数、章节、图表数、关键词频次）
    docx/                 Markdown 源稿 → 学位论文 Word（只用 Python 标准库），学校格式写在配置文件里
    figures/              示意图辅助库与数据图示例（matplotlib），全文统一风格
    check/                文本对比、PDF 版面抽查、目录文字与页码核对
  templates/            决定日志、主题关系、理论映射、证据台账/缺口决策、导师进度、AI 使用说明、范文分析、章节源稿
  example/              虚构企业 YT 公司的示例源稿（含一章完整的现状与问题分析）和绘图脚本
```

## 方法的核心

1. 证据先于文字：实质判断可追溯；证据拿不到时按替代、缩小范围、降低结论强度或调整研究设计处理，不把工作占位带入送审稿
2. 对标本地标准：导师推荐论文和本院范文优先；样本不足时只作描述，不把小样本统计当规范
3. 论证关系贯穿全文：问题、原因、方案和效果可以一对多或多对多，不为对称凑数
4. 理论落到分析：理论要素映射到分析维度、证据、发现和方案
5. 过程外化：证据、判断、导师决定、进度和变更写入文件，不只留在对话里
6. 单一源稿，整份重建：只改 Markdown、配置和绘图脚本，按目标软件核对 Word/WPS 排版
7. 作者提供判断，助手组织表达：记录来源和确认状态；决定沿革追加保留

## 许可

MIT。方法和脚本都可以自由修改使用；用它写出来的论文当然是你自己的。

---

*A skill for AI agents: a method for drafting case-study MBA theses at Chinese universities, with scripts for Markdown-to-Word generation, figure drawing, sample-thesis statistics and TOC checking. Documentation is in Chinese, as is the thesis format it targets.*
