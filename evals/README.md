# 评测

这里的文件用来检查 skill 是否按设计工作，不属于 skill 本体，安装时不用复制。所有用例都是虚构的，不含真实论文或企业材料。

## 文件

| 文件 | 测什么 |
|---|---|
| `trigger_eval.json` | 触发：20 条用户提问，10 条应该用上本 skill，10 条不应该（降 AIGC 率、定量实证、本科论文、期刊论文、教学案例、多案例比较等相近但不在范围内的情形） |
| `evals.json` | 第 1–7 条：入口路由与边界，检查助手是否从正确的阶段切入，以及是否守住“不编造、不帮助规避检测、范围之外如实说明”这些边界。第 8–10 条：虚构案例（见下）。每条带检查点（`expectations`） |
| `cases/` | 3 个虚构案例的材料包。`materials/` 是交给助手的论文工作目录，`answer_key.json` 是标准答案（只给评分用，不能让被测的助手看到），`make_data.py` 用固定随机种子生成企业数据，可重复 |

## 虚构案例

| 案例 | 行业 | 测什么 |
|---|---|---|
| `case-a-restaurant-writing` | 连锁餐饮 | 成文：从门店损耗数据写出 3.3.1 节。数字有标准答案；数据里有供应商名称（不得出现在正文）；大纲要的行业平均值作者没有提供（不得编造） |
| `case-b-logistics-data` | 仓储物流 | 数据解读：企业数据与已写正文有 4 处冲突、1 个统计期间口径陷阱、1 项数据未到位，另有 1 处看似不同其实一致（员工人数） |
| `case-c-bank-review` | 城商行支行 | 整体审查：稿子里预埋 10 个问题（数字不一致、算错、统计期间混用、图号不存在、文献角标不对应、问题与方案不对应、方案数量不符、目标写成结果、脱敏、禁用说法） |

运行时把 `materials/` 复制到每次运行自己的工作目录里，评分时对照 `answer_key.json`，并检查原稿件是否被改动。

## 怎么跑

用 skill-creator 的评测流程（Claude Code 里加载 `skill-creator` skill）：

1. **入口与边界**：对 `evals.json` 的每条提问各开两个子代理，一个先读 `china-mba-case-thesis/SKILL.md` 再回答，一个不读；回复存到 `china-mba-case-thesis-workspace/iteration-N/eval-<id>-<name>/{with_skill,without_skill}/outputs/response.md`。再按检查点评分，写 `grading.json`，用 skill-creator 的 `aggregate_benchmark` 汇总、`generate_review.py` 生成查看页面。
2. **触发**：skill-creator 自带的 `run_eval.py` 依赖 `claude -p` 命令行，且不支持 Windows。不具备条件时用替代做法：每条提问开一个子代理，给它一份可用 skill 列表（本 skill 加 docx、pdf、xlsx、pptx、deep-research、通用 academic-writing 几个干扰项），只问它会加载哪一个，统计与 `should_trigger` 是否一致。替代做法只能检验 description 写得是否清楚，不能代替真实环境里的触发率。

`china-mba-case-thesis-workspace/` 已在 `.gitignore` 里，评测结果不进仓库。

## 结果记录

| 日期 | 版本 | 触发 | 入口与边界（带 skill / 不带） | 备注 |
|---|---|---|---|---|
| 2026-10-11 | iteration-1 | 20/20 | 28/28（100%）/ 17/28（61%） | 触发用替代做法，每条跑 1 次；评分员认为约三分之一的检查点区分度不足，下一轮收紧 |
| 2026-10-11 | iteration-2 | — | 31/34（91%）/ 15/34（44%） | 检查点收紧后重跑，skill 未改；skill 在“举例不放具体数字和企业事实”上失分（第 4、5 题），之后已补规则 |
| 2026-10-11 | iteration-3 | — | 49/52（94%）/ 37/52（71%） | 只跑第 3、4、5、7 题和 3 个虚构案例；skill 已补“举例不放具体数字和企业事实”。案例中不带 skill 时两次直接改稿、一次自行选定口径 |
