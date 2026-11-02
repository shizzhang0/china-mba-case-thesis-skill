import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'china-mba-case-thesis' / 'scripts' / 'docx' / 'build_docx.py'
CONFIG_PATH = ROOT / 'china-mba-case-thesis' / 'scripts' / 'docx' / 'thesis.config.example.json'
spec = importlib.util.spec_from_file_location('build_docx', MODULE_PATH)
build_docx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_docx)


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))

    def test_example_config_is_valid_without_warnings(self):
        self.assertEqual([], build_docx.validate_config(self.cfg))

    def test_unknown_key_warns_about_typo(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['pageNumber'] = cfg.pop('pageNumbers')
        warnings = build_docx.validate_config(cfg)
        self.assertTrue(any('pageNumber' in warning and '未知键' in warning for warning in warnings))

    def test_missing_required_nested_key_is_actionable(self):
        cfg = copy.deepcopy(self.cfg)
        del cfg['page']['marginTw']['left']
        with self.assertRaisesRegex(build_docx.BuildError, r'配置缺少必填项：配置.page.marginTw.left'):
            build_docx.validate_config(cfg)

    def test_wrong_value_type_is_rejected(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['body']['lineSpacing'] = '1.5'
        with self.assertRaisesRegex(build_docx.BuildError, r'配置项 配置.body.lineSpacing 类型错误'):
            build_docx.validate_config(cfg)

    def test_invalid_table_column_weights_are_rejected(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['table']['columnWeightsByCaption']['表 1'] = [1, 0]
        with self.assertRaisesRegex(build_docx.BuildError, '正数权重数组'):
            build_docx.validate_config(cfg)

    def test_example_build_creates_parseable_docx_package(self):
        cfg, base = build_docx.load_config(str(CONFIG_PATH))
        builder = build_docx.Builder(cfg, base)
        sources = builder.load_sources()
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / 'smoke.docx'
            builder.build(str(output), sources)
            with zipfile.ZipFile(output) as docx:
                xml_files = [name for name in docx.namelist() if name.endswith('.xml')]
                self.assertIn('word/document.xml', xml_files)
                for name in xml_files:
                    ET.fromstring(docx.read(name))


if __name__ == '__main__':
    unittest.main()
