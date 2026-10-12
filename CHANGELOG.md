# Changelog

## 未发布

- 配套脚本统一为只需 Python：
  - Word 生成改为 `docx/build_docx.py`，只用标准库直接写 OOXML，替代 Node.js 的 `build_docx.js`；配置文件格式和源稿约定不变
  - `figlib.py` 改用 matplotlib 绘制，不再需要 playwright 和 Chrome / Chromium；接口不变，西文字符用 Times New Roman，加粗用描边模拟
  - `docx_text_diff.py`：run 里的制表符计入文字，pPr 里的制表位定义不计

## 0.1.0（2026-10-11）

首个公开版本。


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
- 不编造规则补充：举例、问询稿和修改指引里不放能直接搬进正文的具体数字或企业事实；行业或公开数据只能作参照，不能顶替企业数据
- 新增 `evals/`：20 条触发测试、7 条入口与边界测试、3 个虚构案例（成文、数据解读、整体审查），附标准答案与数据生成脚本
- README 定稿：去掉“施工中”标注，补充获取方式、Windows 安装路径和评测摘要
