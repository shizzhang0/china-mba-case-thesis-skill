# Changelog

## 0.1.0（2026-10-12）

首个公开版本。

### 包含什么

- **skill 本体** `china-mba-case-thesis/`：方法总纲 `SKILL.md`（助手的角色与边界、六条原则、从哪里进入、每次开工先做的事、文件管理、六个阶段），各阶段细则 `references/`，决定日志与章节源稿模板 `templates/`，虚构企业“YT 公司注塑件质量管理改进研究”的示例源稿和绘图脚本 `example/`
- **配套脚本**，只需 Python 3.8 以上：Markdown 源稿生成学位论文 Word（只用标准库）、范文横向统计、示意图库与数据图示例（matplotlib）、两版 Word 文本对比、目录文字与页码核对、快照、版面抽查（需 LibreOffice，未在 Windows 实测）
- **评测** `evals/`：20 条触发测试、7 条入口与边界测试、3 个虚构案例（成文、数据解读、整体审查），附标准答案与数据生成脚本

### 相对原始素材（`case-thesis-drafting-method`）的主要变化

- 更名为 `china-mba-case-thesis`（仓库 `china-mba-case-thesis-skill`），仓库改为两层结构：根目录放 README、LICENSE、CHANGELOG、evals，skill 本体放在 `china-mba-case-thesis/`
- 定位调整：新增“助手的角色与边界”（作者对核心分析和最终文字负责、提醒学校 AI 写作规定、不帮助规避 AIGC 检测）和“从哪里进入”（按作者所处阶段选择起点）；description 写明适用范围与不适用情形
- 示例和参考文件里的举例全部换成中性的虚构内容；配置样例的格式取值改为通用示意，不对应任何学校的规范
- 不编造规则补充：举例、问询稿和修改指引里不放能直接搬进正文的具体数字或企业事实；行业或公开数据只能作参照，不能顶替企业数据
- 配套脚本统一为只需 Python：Word 生成由 Node.js 改为 Python 标准库实现，配置格式和源稿约定不变；示意图库改用 matplotlib，不再需要 playwright 和 Chrome
- 脚本在 Windows 11 上实测并修复：Python 脚本统一以 UTF-8 输出；Word 生成自动创建输出目录；范文统计修复 pdftotext 丢中文、打不开中文路径、页数多算 1 页，提取失败时改用 pdfminer 并提示；版面抽查修正 Windows 下的文件 URL 和 soffice 路径；文本对比计入文字中的制表符
