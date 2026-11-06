#!/usr/bin/env python3
"""读取本机员工配置，向业务工作目录生成待粘贴的WPS脚本。"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(rules_path, output_path):
    rules = json.loads(Path(rules_path).read_text(encoding='utf-8-sig'))
    names = list(dict.fromkeys([*rules['employee_codes'].values(), rules['unassigned_employee']]))
    if not names or not all(isinstance(name, str) and name.strip() for name in names):
        raise ValueError('员工配置包含空白或无效姓名')
    template = ROOT / 'scripts/wps-performance-sync.js'
    output = Path(output_path).resolve()
    if output == template.resolve():
        raise ValueError('输出须保存到业务工作目录，不能覆盖技能内的公开模板')
    content = template.read_text(encoding='utf-8-sig')
    replacement = 'const PERFORMANCE_MEMBERS = ' + json.dumps(names, ensure_ascii=False) + ';'
    content, count = re.subn(r'^const PERFORMANCE_MEMBERS = .*;$', lambda _: replacement, content, count=1, flags=re.M)
    if count != 1:
        raise ValueError('找不到WPS脚本中的员工配置行，未生成文件')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', required=True, help='业务工作目录内的private-rules.json')
    parser.add_argument('--output', default='out/wps-performance-sync.js')
    args = parser.parse_args()
    try:
        output = prepare(args.rules, args.output)
        print('WPS脚本已生成：' + str(output) + '；请粘贴到本人目标文档的共享脚本。')
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, '脚本未生成：' + str(exc) + '\n')


if __name__ == '__main__':
    main()
