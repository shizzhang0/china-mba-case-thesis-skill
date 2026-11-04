import importlib.util
import io
import pathlib
import tempfile
import unittest
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
        self.assertTrue(r['order_issues'] and '[2]' in r['order_issues'][0])

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


def work(title, family, year, volume=None, issue=None, page=None, doi=None):
    return {'title': [title], 'author': [{'family': family, 'given': 'X'}],
            'issued': {'date-parts': [[year]]}, 'volume': volume, 'issue': issue,
            'page': page, 'container-title': ['Journal'], 'DOI': doi}


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

    def test_only_spec(self):
        self.assertEqual({1, 3, 4, 5}, crossref_check.parse_only('1,3-5'))


if __name__ == '__main__':
    unittest.main()
