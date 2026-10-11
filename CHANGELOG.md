# Changelog

## 未发布

- 从 `case-thesis-drafting-method` 更名为 `china-mba-case-thesis`（仓库名 `china-mba-case-thesis-skill`）
- 仓库改为两层结构：根目录放 README、LICENSE、CHANGELOG、evals；skill 本体放在 `china-mba-case-thesis/`
- 定位调整：SKILL.md 新增“助手的角色与边界”（作者对核心分析和最终文字负责、提醒学校 AI 写作规定、不帮助规避 AIGC 检测）和“从哪里进入”（按作者所处阶段选择起点）；description 写明适用范围与不适用情形
- 示例改为“YT 公司注塑件质量管理改进研究”（全面质量管理 + PDCA），参考文件中的举例统一改为中性示例
- 配置样例的格式取值改为通用示意，不对应任何学校的规范
- 脚本在 Windows 上实测并修复：
  - Python 脚本统一以 UTF-8 输出，修复输出被重定向时打印中文报错
  - `build_docx.js` 自动创建输出目录
  - `survey_samples.py`：pdftotext 加 `-enc UTF-8`（xpdf 版默认丢中文）、绕开中文路径、失败时改用 pdfminer 并给出提示、页数不再多算 1 页
  - `figlib.py`：文件地址改用标准 file URL，SVG 统一 LF 换行
  - `render_pdf.py`：Windows 下的文件 URL 和 soffice 路径
