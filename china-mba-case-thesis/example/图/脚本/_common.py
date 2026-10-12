"""让示例脚本能找到 scripts/figures/figlib.py；实际项目里把 figlib.py 复制到图脚本目录即可。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scripts', 'figures'))
