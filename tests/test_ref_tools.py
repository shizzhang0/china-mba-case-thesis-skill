import importlib.util
import io
import pathlib
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout, redirect_stderr


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = ROOT / 'china-mba-case-thesis' / 'scripts' / 'check'
EXAMPLE_SRC = ROOT / 'china-mba-case-thesis' / 'example' / 'src'


def load(name):
    spec = importlib.util.spec_from_file_location(name, CHECK / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ref_check = load('ref_check')
crossref_check = load('crossref_check')

REFS = '# 参考文献\n\n[1] 甲. 题一[J]. 刊, 2020, 1(1): 1-2.\n[2] 乙. 题二[J]. 刊, 2021, 1(1): 1-2.\n[3] 丙. 题三[J]. 刊, 2022, 1(1): 1-2.\n'


class ParseCiteTests(unittest.TestCase):
    def test_supported_forms(self):
        self.assertEqual(([1], False), ref_check.parse_cite('[1]'))
        self.assertEqual(([1, 3], False), ref_check.parse_cite('[1][3]'))
        self.assertEqual(([1, 3], False), ref_check.parse_cite('[1,3]'))
        self.assertEqual(([1, 3], False), ref_check.parse_cite('[1，3]'))
        self.assertEqual(([2, 3, 4], True), ref_check.parse_cite('[2-4]'))
        self.assertEqual(([2, 3, 4], True), ref_check.parse_cite('[2–4]'))
        self.assertEqual(([1, 5, 6, 7], True), ref_check.parse_cite('[1, 5-7]'))

    def test_non_numeric_superscript_ignored(self):
        self.assertEqual(([], False), ref_check.parse_cite('2'))
        self.assertEqual(([], False), ref_check.parse_cite('[a]'))
        self.assertEqual(([], False), ref_check.parse_cite('[4-2]'))


class RefCheckTests(unittest.TestCase):
    def run_check(self, chapters, refs=REFS):
        return ref_check.check(chapters, refs)

    def test_clean_document(self):
        r = self.run_check([('第1章.md', '## 1.1　背景\n\n甲说<sup>[1]</sup>。乙说<sup>[2][3]</sup>。\n')])
        self.assertFalse(ref_check.has_errors(r))
        self.assertEqual([1, 2, 3], r['first_order'])

    def test_missing_unused_and_order(self):
        r = self.run_check([('第1章.md', '先引<sup>[2]</sup>，再引<sup>[1]</sup>，又引<sup>[9]</sup>。\n')])
        self.assertEqual([9], r['missing'])
        self.assertEqual([3], r['unused'])
        self.assertEqual([1], [x['n'] for x in r['late']])
        self.assertEqual(2, r['late'][0]['after'])

    def test_all_order_problems_reported_and_grouped(self):
        r = self.run_check([('第1章.md', '早引<sup>[3]</sup>。后来<sup>[1]</sup>和<sup>[2]</sup>。\n')])
        self.assertEqual([1, 2], [x['n'] for x in r['late']])
        text = ref_check.report(r)
        self.assertIn('首次出现顺序：2', text)
        self.assertIn('[3]（第1章.md:1 首次出现）之后才首次出现的编号 2 个', text)

    def test_pair_range_form(self):
        self.assertEqual(([2, 3, 4], True), ref_check.parse_cite('[2]-[4]'))

    def test_range_only_flagged_for_padding_review(self):
        r = self.run_check([('第1章.md', '研究很多<sup>[1-3]</sup>。甲说<sup>[1]</sup>。\n')])
        self.assertEqual([2, 3], r['range_only'])

    def test_notes_todo_and_code_skipped_but_source_notes_kept(self):
        md = ('> 依据：草稿<sup>[3]</sup>\n'
              '正文<sup>[1]</sup>。\n'
              '> 资料来源：文献<sup>[2]</sup>。\n'
              '```\n代码<sup>[3]</sup>\n```\n'
              '## 本章待补\n待补<sup>[3]</sup>\n')
        r = self.run_check([('第1章.md', md)])
        self.assertEqual([1, 2], r['first_order'])
        self.assertEqual([3], r['unused'])

    def test_bare_bracket_citation_reported(self):
        r = self.run_check([('第1章.md', '甲说[1]。乙说<sup>[2]</sup>，丙说<sup>[3]</sup>。见 [需补充：数据]。\n')])
        self.assertEqual(['[1]'], [b['text'] for b in r['bare']])

    def test_reference_list_problems(self):
        refs = ('[1] 甲. Same title[J]. 刊, 2020.\n[3] 乙. Same Title[J]. 刊, 2021.\n[3] 丙. 题[J]. 刊, 2022.\n')
        _, issues = ref_check.parse_refs(refs)
        text = '\n'.join(issues)
        self.assertIn('重复', text)
        self.assertIn('不连续', text)
        self.assertIn('疑似重复条目', text)

    def test_cli_on_example_passes_and_reports_positions(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / '引用核对.md'
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                code = ref_check.main([str(EXAMPLE_SRC), '-o', str(out)])
            self.assertEqual(0, code)
            text = out.read_text(encoding='utf-8')
            self.assertIn('第2章-理论基础.md', text)
            self.assertIn('| [5] | 1 |', text)


WHOLE = """# 目录
参考文献

# 第1章 绪论
研究很多[1][2]，采购组合模型由 Kraljic 提出[3]。见[4]-[5]。

# 第2章 理论
Kraljic 矩阵把物料分为四类[5]。
# 参考文献
[1] 甲. 题一[J]. 刊, 2020.
[2] 乙. 题二[J]. 刊, 2020.
[3] Kraljic P. Purchasing must become supply management[J]. HBR, 1983.
[4] 丁. 题四[J]. 刊, 2020.
[5] 戊. 题五[J]. 刊, 2020.
[6] 己. 题六[J]. 刊, 2020.
# 致谢
谢谢。
"""


class ExternalDraftTests(unittest.TestCase):
    def test_split_single_uses_last_refs_heading_and_keeps_line_numbers(self):
        body, refs = ref_check.split_single(WHOLE)
        self.assertEqual(6, len(ref_check.parse_refs(refs)[0]))
        self.assertEqual(len(WHOLE.splitlines()), len(body.splitlines()))
        self.assertIn('谢谢', body)
        self.assertNotIn('[6] 己', body)

    def test_bare_citations_auto_plain(self):
        body, refs = ref_check.split_single(WHOLE)
        r = ref_check.check([('论文.md', body)], refs)
        self.assertTrue(r['auto_plain'])
        self.assertEqual([6], r['unused'])
        self.assertEqual([], r['missing'])
        self.assertEqual([], r['late'])
        self.assertEqual([], r['bare'])
        self.assertIn('已自动按 --plain 处理', ref_check.report(r))

    def test_bare_only_flagged_when_sup_present_unless_plain(self):
        refs = '[1] a[J].\n[2] b[J].\n'
        r = ref_check.check([('a.md', '甲<sup>[1]</sup>，乙[2]。')], refs)
        self.assertFalse(r['plain'])
        self.assertEqual(['[2]'], [b['text'] for b in r['bare']])
        r = ref_check.check([('a.md', '甲<sup>[1]</sup>，乙[2]。')], refs, plain=True)
        self.assertEqual([], r['unused'])

    def test_terms_tie_keyword_to_its_clause(self):
        body, refs = ref_check.split_single(WHOLE)
        r = ref_check.check([('论文.md', body)], refs, terms=['Kraljic', 'BPR'])
        self.assertEqual([3, 5], list(r['terms']['Kraljic']))
        self.assertEqual([], list(r['terms']['BPR']))

    def test_terms_prefer_nearest_following_citation(self):
        md = '本文结合供应商全生命周期管理理论[41][43]和Kraljic矩阵[12]，构建分析框架。根据[7]的COSO框架，设计控制点。'
        refs = ''.join(f'[{n}] 题{n}[J].\n' for n in range(1, 44))
        r = ref_check.check([('a.md', md)], refs, plain=True, terms=['Kraljic', 'COSO'])
        self.assertEqual([12], list(r['terms']['Kraljic']))
        self.assertEqual([7], list(r['terms']['COSO']))   # 其后没有角标时退回整个分句

    def test_refs_title_variants(self):
        for title in ('主要参考文献', '参考文献：', '## 参考文献:'):
            body, refs = ref_check.split_single(f'正文[1]。\n{title}\n[1] 甲. 题一[J]. 刊, 2020.\n')
            self.assertIsNotNone(refs, title)
            self.assertEqual([1], list(ref_check.parse_refs(refs)[0]))
        self.assertIsNone(ref_check.split_single('正文[1]。\nReferences\n[1] A. B[J].\n')[1])
        body, refs = ref_check.split_single('正文[1]。\nReferences\nA. B[J]. 2020.\n', title='References')
        self.assertEqual({1: 'A. B[J]. 2020.'}, dict(ref_check.parse_refs(refs)[0]))

    def test_auto_numbered_reference_list(self):
        refs, issues = ref_check.parse_refs('参考文献\n甲. 题一[J]. 刊, 2020.\n乙. 题二[J]. 刊, 2020.\n')
        self.assertEqual([1, 2], list(refs))
        self.assertIn('自动编号', issues[0])

    def test_docx_superscript_citations(self):
        ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        sup = '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'

        def para(*runs, style=None):
            ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
            return '<w:p>' + ppr + ''.join(runs) + '</w:p>'

        def run(t, is_sup=False):
            return '<w:r>' + (sup if is_sup else '') + f'<w:t>{t}</w:t></w:r>'

        doc = (f'<w:document {ns}><w:body>'
               + para(run('第1章 绪论'), style='1')
               + para(run('甲说'), run('[', True), run('2]', True), run('，乙说[9]。'))
               + para(run('丙说'), run('[1]', True), run('。'))
               + para(run('参考文献'), style='1')
               + para(run('[1] 甲. 题一[J]. 刊, 2020.'))
               + para(run('[2] 乙. 题二[J]. 刊, 2020.'))
               + '</w:body></w:document>')
        styles = f'<w:styles {ns}><w:style w:styleId="1"><w:name w:val="heading 1"/></w:style></w:styles>'
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / '稿件.docx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', doc)
                z.writestr('word/styles.xml', styles)
            md = ref_check.read(str(path))
            self.assertIn('# 第1章 绪论', md)
            self.assertIn('<sup>[2]</sup>', md)
            out = io.StringIO()
            with redirect_stderr(io.StringIO()), redirect_stdout(out):
                code = ref_check.main([str(path)])
        self.assertEqual(1, code)   # [2] 先于 [1] 出现
        text = out.getvalue()
        self.assertIn('只认 <sup> 角标', text)
        self.assertIn('首次出现顺序：1', text)
        self.assertIn('稿件.docx:2 [9]', text)

    def test_docx_character_style_superscript_and_textboxes(self):
        ns = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
              'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')
        cite_style = '<w:rPr><w:rStyle w:val="Cite"/></w:rPr>'
        textbox = ('<w:txbxContent><w:p><w:r><w:t>图中文字</w:t></w:r></w:p></w:txbxContent>')
        drawing = ('<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing>' + textbox
                   + '</w:drawing></mc:Choice><mc:Fallback><w:pict>' + textbox
                   + '</w:pict></mc:Fallback></mc:AlternateContent></w:r>')
        doc = (f'<w:document {ns}><w:body>'
               '<w:p><w:r><w:t>甲说</w:t></w:r><w:r>' + cite_style + '<w:t>[1]</w:t></w:r>'
               '<w:r><w:t>。</w:t></w:r>' + drawing + '</w:p>'
               '</w:body></w:document>')
        styles = (f'<w:styles {ns}>'
                  '<w:style w:type="character" w:styleId="Sup"><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'
                  '<w:style w:type="character" w:styleId="Cite"><w:basedOn w:val="Sup"/></w:style>'
                  '</w:styles>')
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'a.docx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', doc)
                z.writestr('word/styles.xml', styles)
            md = ref_check.read(str(path))
        self.assertEqual(['甲说<sup>[1]</sup>。', '图中文字'], md.splitlines())


def work(title, family, year, volume=None, issue=None, page=None, doi=None, article_number=None):
    w = {'title': [title], 'author': [{'family': family, 'given': 'X'}],
         'issued': {'date-parts': [[year]]}, 'volume': volume, 'issue': issue,
         'page': page, 'container-title': ['Journal'], 'DOI': doi}
    if article_number:
        w['article-number'] = article_number
    return w


class CrossrefParseTests(unittest.TestCase):
    def test_parse_journal_entry(self):
        e = crossref_check.parse_entry('Parasuraman A, Zeithaml V A, Berry L L. A conceptual model of service quality'
                                       '[J]. Journal of Marketing, 1985, 49(4): 41-50.')
        self.assertEqual('Parasuraman', e['first_family'])
        self.assertEqual('A conceptual model of service quality', e['title'])
        self.assertEqual(('J', 'Journal of Marketing', '1985', '49', '4', '41-50'),
                         (e['type'], e['journal'], e['year'], e['volume'], e['issue'], e['pages']))

    def test_parse_doi_and_book(self):
        e = crossref_check.parse_entry('Barney J. Firm resources[J]. Journal of Management, 1991, 17(1): 99-120. '
                                       'DOI:10.1177/014920639101700108.')
        self.assertEqual('10.1177/014920639101700108', e['doi'])
        self.assertEqual('99-120', e['pages'])
        b = crossref_check.parse_entry('Deming W E. Out of the crisis[M]. Cambridge, MA: MIT, 1986.')
        self.assertEqual(('M', '1986', 'Out of the crisis'), (b['type'], b['year'], b['title']))

    def test_chinese_entry_detected(self):
        self.assertTrue(crossref_check.is_chinese(crossref_check.parse_entry('张三. 质量管理研究[J]. 管理世界, 2020, 1(1): 1-2.')))


class CrossrefJudgeTests(unittest.TestCase):
    E = crossref_check.parse_entry('Smith J. Quality and trust: a study[J]. Journal, 2020, 5(2): 10-20.')

    def test_exact_match_passes(self):
        r = crossref_check.judge(self.E, [work('Quality and Trust: A Study', 'Smith', 2020, '5', '2', '10-20')])
        self.assertEqual('通过', r['status'])

    def test_subtitle_joined(self):
        w = work('Quality and trust', 'Smith', 2020, '5', '2', '10-20')
        w['subtitle'] = ['a study']
        self.assertEqual('通过', crossref_check.judge(self.E, [w])['status'])

    def test_field_mismatch_listed(self):
        r = crossref_check.judge(self.E, [work('Quality and trust: a study', 'Smith', 2021, '5', '3', '10-21')])
        self.assertEqual('有出入', r['status'])
        self.assertEqual({'年', '期', '页码'}, {d[0] for d in r['diffs']})

    def test_similar_title_is_not_a_pass(self):
        r = crossref_check.judge(self.E, [work('Quality and trust: a survey', 'Smith', 2020)])
        self.assertEqual('仅相近', r['status'])

    def test_unrelated_is_not_found(self):
        self.assertEqual('未查到', crossref_check.judge(self.E, [work('Blockchain logistics', 'Lee', 2020)])['status'])
        self.assertEqual('未查到', crossref_check.judge(self.E, [])['status'])

    def test_run_with_stub_query_and_render(self):
        refs = ('[1] Smith J. Quality and trust: a study[J]. Journal, 2020, 5(2): 10-20.\n'
                '[2] 张三. 质量管理研究[J]. 管理世界, 2020, 1(1): 1-2.\n'
                '[3] Lee K. Unknown paper[J]. Journal, 2020, 1(1): 1-2.\n')

        def stub(e, mailto):
            if e['first_family'] == 'Lee':
                raise OSError('network down')
            return [work('Quality and trust: a study', 'Smith', 2020, '5', '2', '10-20')], 'stub://1'

        rows = crossref_check.run(refs, query_fn=stub, delay=0)
        self.assertEqual(['通过', '跳过', '查询失败'], [r['status'] for r in rows])
        text = crossref_check.render(rows)
        self.assertIn('统计：通过 1，查询失败 1，跳过 1', text)
        self.assertIn('stub://1', text)

    def test_article_number_instead_of_pages(self):
        e = crossref_check.parse_entry('Smith J. Quality and trust: a study[J]. Journal, 2020, 5(2): 1-17.')
        r = crossref_check.judge(e, [work('Quality and trust: a study', 'Smith', 2020, '5', '2', article_number='1234')])
        self.assertEqual('有出入', r['status'])
        self.assertIn('文章编号 1234', r['diffs'][0][2])
        e = crossref_check.parse_entry('Smith J. Quality and trust: a study[J]. Journal, 2020, 5(2): 1234.')
        r = crossref_check.judge(e, [work('Quality and trust: a study', 'Smith', 2020, '5', '2', article_number='1234')])
        self.assertEqual('通过', r['status'])

    def test_pages_unchecked_is_noted(self):
        r = crossref_check.judge(self.E, [work('Quality and trust: a study', 'Smith', 2020, '5', '2')])
        self.assertEqual('通过', r['status'])
        self.assertIn('页码未比对', r['note'])

    def test_surname_prefixes(self):
        e = crossref_check.parse_entry('van der Berg J, Lee K. Quality and trust: a study[J]. Journal, 2020, 5(2): 10-20.')
        self.assertEqual('van der Berg', e['first_family'])
        for fam in ('van der Berg', 'Van Der Berg', 'Berg'):
            r = crossref_check.judge(e, [work('Quality and trust: a study', fam, 2020, '5', '2', '10-20')])
            self.assertEqual('通过', r['status'], fam)
        r = crossref_check.judge(e, [work('Quality and trust: a study', 'Smith', 2020, '5', '2', '10-20')])
        self.assertEqual('有出入', r['status'])

    def test_only_spec(self):
        self.assertEqual({1, 3, 4, 5}, crossref_check.parse_only('1,3-5'))


if __name__ == '__main__':
    unittest.main()
