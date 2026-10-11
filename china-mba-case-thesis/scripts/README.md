# 配套脚本

都是可选工具：方法论本身不依赖它们，但用它们可以把“单一源稿、整份重建”、快照回退和合稿检查做成固定流程。

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `snapshot.py` | 大改前把工作目录打成一个带日期和事件名的 zip 放进 `归档/`，代替复制加后缀 | Python 3 |
| `survey/survey_samples.py` | 阶段 1 用：批量统计范文 PDF 的页数、章节骨架、图表数、文献数、关键词频次，输出一张表 | pdftotext（poppler）或 pdfminer.six |
| `docx/build_docx.js` | 按配置把 Markdown 源稿整份生成 Word：分节、罗马/阿拉伯页码、页眉页脚、目录域、标题样式、三线表、图表题、图注表注、角标、参考文献 | Node.js 18+，`npm install` |
| `docx/thesis.config.example.json` | 配置样例：路径、学校格式、封面版式。复制一份改成本校规范和自己的信息 | — |
| `figures/figlib.py` | 示意图辅助库：方框、折线箭头、菱形、编号圆点、红叉；统一字体与配色；SVG → 2 倍 PNG | `pip install playwright`，Chromium |
| `figures/example_diagram.py` | 示意图写法示例（一图一脚本） | 同上 |
| `figures/example_datachart.py` | 数据图示例：灰度柱 + 黑色折线双轴，脚本内断言核对合计；自动找系统中文字体 | matplotlib |
| `figures/extract_cjk_font.py` | Linux 上从 CJK 字体集合（.ttc）取出简体中文字形，供 matplotlib 使用；Windows 有宋体时不需要 | fonttools |
| `check/docx_text_diff.py` | 两版 docx 按句对比正文文字，确认只有预期改动 | Python 3 |
| `check/render_pdf.py` | LibreOffice 更新目录后导出 PDF，可出缩略图，抽查版面（页码以 Word 为准） | LibreOffice 及其 Python UNO；缩略图需 poppler 的 pdftoppm |
| `check/toc_check.py` | 核对 Word 保存后的目录：条目文字与正文标题是否一致；页码与分页标记推算是否一致，跨页表格自动修正 | Python 3 |

## 平台说明

- **Windows**（已在 Windows 11 实测，`render_pdf.py` 除外）：
  - 命令里的 `python3` 换成 `python`。
  - 画图脚本直接用系统的宋体，不需要 `extract_cjk_font.py`。
  - Chromium 可以用已装的 Chrome：设环境变量 `CHROMIUM_PATH` 指向 chrome.exe（如 `C:\Program Files\Google\Chrome\Application\chrome.exe`），否则要先运行 `playwright install chromium` 下载一份。
  - `survey_samples.py` 可用 Git for Windows 自带的 pdftotext（xpdf 版），脚本已处理它的中文编码和中文路径问题。
  - `render_pdf.py` 要用 LibreOffice 自带的 Python 运行：`"C:\Program Files\LibreOffice\program\python.exe" render_pdf.py ...`；缩略图需要另装 poppler 的 pdftoppm。尚未在 Windows 上实测。
- **Linux / 云端**：没有宋体和 Times New Roman，LibreOffice 排出的页码会和 Word 差一两页，只用来看版面。

## 快速试跑

```bash
pip install playwright matplotlib                 # 只需一次；也可以用 uv run --with playwright --with matplotlib 临时运行
cd scripts/figures && python3 example_diagram.py && python3 example_datachart.py   # 输出到 out/
cd ../docx && npm install && node build_docx.js thesis.config.example.json 示例.docx
python3 ../check/docx_text_diff.py 示例.docx 示例.docx
python3 ../snapshot.py ../../example 试跑
```

示例源稿在 `example/src/`，演示了源稿约定的全部写法。

## 生成规则（与 references/源稿约定.md 一致）

- 章文件按 `files.chapterPattern` 匹配（默认“第N章…md”），按章号排序；摘要文件里 `# Abstract` 之后是英文摘要
- 图片：源稿里 `![图 x.x](路径)` 的路径存在就用它（相对源稿目录）；否则按“图x.x_”前缀到 `paths.img` 下找 PNG。单张图宽度可在 `figures.widthsPx` 里指定
- 只有 `> 资料来源…`、`> 注…` 作为图注、表注输出；其他 `>` 行是写作备注
- 匹配 `cutSectionPattern` 的二级标题（默认“## 本章待…”）及其后内容不输出
- 生成的文件只有目录域、没有目录内容：要在 Word 里解除受保护视图 → 更新整个目录 → 原文件名保存
