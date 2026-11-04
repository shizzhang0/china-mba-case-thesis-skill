# 配套脚本

都是可选工具：方法论本身不依赖它们，但用它们可以把“单一源稿、整份重建”、快照回退和合稿检查做成固定流程。

全部脚本只需要 **Python 3.8 以上**。Word 生成、快照、文本对比、目录核对、引用核对只用标准库；画图要 `pip install matplotlib`。

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `snapshot.py` | 大改前把工作目录打成一个带日期和事件名的 zip 放进 `归档/`，打印文件数和未压缩体积；可用 `--exclude-dir 参考论文` 明确排除大目录 | 标准库 |
| `survey/survey_samples.py` | 阶段 1 用：批量统计范文 PDF 的页数、章节骨架、图表数、文献数、关键词频次，输出一张表 | pdftotext（poppler / xpdf）或 `pip install pdfminer.six` |
| `docx/build_docx.py` | 按配置把 Markdown 源稿整份生成 Word：分节、罗马/阿拉伯页码、页眉页脚、目录（条目预填，页码由排版软件更新）、标题样式、三线表、图表题、图注表注、角标、参考文献、附录与致谢；表格默认按内容估算列宽，也支持按表题配置列宽；生成后打印各章汉字数。也可在别的脚本里导入（用法见文件开头说明） | 标准库 |
| `docx/thesis.config.example.json` | 配置样例：路径、学校格式、封面版式。复制一份改成本校规范和自己的信息 | — |
| `figures/figlib.py` | 示意图辅助库：方框、折线箭头、菱形、编号圆点、红叉；统一字体与配色；输出 SVG 和 2 倍分辨率 PNG | matplotlib |
| `figures/example_diagram.py` | 示意图写法示例（一图一脚本） | 同上 |
| `figures/example_datachart.py` | 数据图示例：灰度柱 + 黑色折线双轴，脚本内断言核对合计；自动找系统中文字体 | matplotlib |
| `figures/extract_cjk_font.py` | Linux 上从 CJK 字体集合（.ttc）取出简体中文字形，供 matplotlib 使用；Windows 有宋体时不需要 | fonttools |
| `check/docx_text_diff.py` | 两版 docx 按句对比正文文字，确认只有预期改动 | 标准库 |
| `check/render_pdf.py` | LibreOffice 更新目录后导出 PDF，可出缩略图，抽查版面（页码以 Word 为准） | LibreOffice 及其 Python UNO；缩略图需 poppler 的 pdftoppm |
| `check/toc_check.py` | 核对 DOCX 目录：条目文字与正文标题是否一致；存在 `lastRenderedPageBreak` 时推算页码，跨页表格自动修正；没有标记时明确报告“页码未验证” | 标准库 |
| `check/ref_check.py` | 核对源稿角标与参考文献表：缺号、未引用、首次出现顺序、文献表编号与疑似重复条目、疑似漏加上标的 `[n]`；列出每条文献被引的位置和句子，标出只在 `[3-15]` 这类区间里出现的文献，供人工判断引用是否相干。解析规则与 `build_docx.py` 一致 | 标准库 |
| `check/crossref_check.py` | 把英文文献的题名（有 DOI 的用 DOI）批量送 Crossref，比对第一作者、年、卷、期、页码，输出《参考文献核对清单》初稿：通过 / 有出入 / 仅相近 / 未查到 / 跳过（中文）/ 查询失败。只有完全吻合才算通过。会把题名、第一作者和 DOI 发给 api.crossref.org；需联网 | 标准库 |

## 平台说明

- **Windows**（已在 Windows 11 实测，`render_pdf.py` 除外）：
  - 命令里的 `python3` 换成 `python`。
  - 画图脚本直接用系统的宋体和 Times New Roman，不需要 `extract_cjk_font.py`。
  - `survey_samples.py` 可用 Git for Windows 自带的 pdftotext（xpdf 版），脚本已处理它的中文编码和中文路径问题。
  - `render_pdf.py` 要用 LibreOffice 自带的 Python 运行：`"C:\Program Files\LibreOffice\program\python.exe" render_pdf.py ...`；缩略图需要另装 poppler 的 pdftoppm。尚未在 Windows 上实测。
- **macOS**：未实测。系统有宋体（Songti SC），画图可用；Word 里的“宋体”会被替换，按学校要求另装字体。
- **Linux / 云端**：未实测。没有宋体和 Times New Roman，画图前先装 Noto Serif CJK（或用 `extract_cjk_font.py`）；LibreOffice 排出的页码会和 Word 差一两页，只用来看版面。

## 快速试跑

```bash
pip install matplotlib                            # 只需一次，画图用；Word 生成不需要装任何包
cd scripts/figures && python3 example_diagram.py && python3 example_datachart.py   # 输出到 out/
cd ../docx && python3 build_docx.py thesis.config.example.json 示例.docx
python3 ../check/docx_text_diff.py 示例.docx 示例.docx
python3 ../snapshot.py ../../example 试跑
python3 ../check/ref_check.py ../../example/src         # 角标与文献表核对
```

示例源稿在 `example/src/`，演示了源稿约定的全部写法。

## 生成规则（与 references/源稿约定.md 一致）

- 章文件按 `files.chapterPattern` 匹配（默认“第N章…md”），按章号排序；摘要文件里 `# Abstract` 之后是英文摘要
- 图片：源稿里 `![图 x.x](路径)` 的路径存在就用它（相对源稿目录）；否则按“图x.x_”前缀到 `paths.img` 下找 PNG。单张图宽度可在 `figures.widthsPx` 里指定
- 只有 `> 资料来源…`、`> 注…` 作为图注、表注输出；其他 `>` 行是写作备注
- 匹配 `cutSectionPattern` 的二级标题（默认“## 本章待…”）及其后内容不输出
- `extraFrontFiles` 里的源稿排在摘要之前；`extraBackFiles` 里的源稿（附录、致谢等）排在参考文献之后，各占一节，一级标题进目录，页眉用该标题
- 配置加载时检查核心键、嵌套结构和类型；未知键会警告（可发现常见拼写错误），不认识的配置键不会被使用
- 汉字数只数汉字，不含写作备注、图片行和章末待办，与 Word 的“字数统计”口径不完全相同
- 目录条目按标题预填，但页码要排版软件计算：在 Word/WPS 里解除受保护视图（如有）→ 更新整个目录 → 原文件名保存；页码核对结果仍按本 README 的状态规则报告
- 表格列宽默认按单元格文字长度估算；需要调整时，在配置的 `table.columnWeightsByCaption` 按完整表题（如 `表 3.1　指标对比`）设置相对权重，例如 `[1, 2, 3]`。权重数量必须与表格列数一致且都为正数；调整源配置后重新生成，避免直接改 Word 导致下次重建丢失。

## WPS 与目录页码

快照默认包含 `参考论文/` 等用户资料目录。运行前会报告文件数和未压缩体积；确需排除时显式使用 `--exclude-dir 参考论文`，并确认被排除资料另有保存。

`toc_check.py` 可检查 DOCX 中保存的目录文字。页码推算依赖排版软件写入 `lastRenderedPageBreak`；Word 与 WPS 的 DOCX 保存结果可能不同，项目不保证两者都会写入该标记。脚本没有标记时会输出“页码未验证”，这不等于页码错误，也不等于页码正确。

若在 WPS 中工作：更新整个目录并保存后运行脚本。若仍显示“未验证”，在 WPS 中逐项对照目录和正文页码；至少检查各章节首个标题、分节/页码重启处、跨页表格之后的标题，以及发现过版面变化的页面。在交付记录中写明“文字核对结果”和“页码核验状态”，不得把未验证描述为通过。Word 环境同样遵守此状态标记和人工复核要求。
