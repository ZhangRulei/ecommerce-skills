#!/usr/bin/env python3
"""仅打包明确列出的公开技能文件，生成WorkBuddy导入包。"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/employee-performance-wps'
FILES = (
    'SKILL.md', 'agents/openai.yaml', '.gitignore',
    'config/rules.json', 'config/credentials.example.env',
    'references/calculation.md', 'references/report-layout.md', 'references/wps-setup.md',
    'scripts/calculate.py', 'scripts/wps_push.mjs', 'scripts/wps-performance-sync.js',
    'scripts/prepare_wps_script.py', 'scripts/test_calculate.py',
    'scripts/test_wps_sync.mjs', 'scripts/test_wps_client.mjs',
    'examples/demo_orders.csv', 'examples/expected_controls.json',
)


def main():
    rules = json.loads((SKILL / 'config/rules.json').read_text(encoding='utf-8'))
    if rules.get('employee_mapping_kind') != 'synthetic_example':
        raise ValueError('只能打包公开示例配置')
    if any(line.split('=', 1)[1].strip() for line in (SKILL / 'config/credentials.example.env').read_text(encoding='utf-8').splitlines() if '=' in line and not line.lstrip().startswith('#')):
        raise ValueError('凭据示例须全部留空')
    destination = ROOT / 'packages/employee-performance-wps-workbuddy.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w') as archive:
        for relative in FILES:
            content = (SKILL / relative).read_bytes()
            if relative == 'SKILL.md':
                body = content.decode('utf-8').split('---', 2)[2].lstrip()
                metadata = {
                    'name': 'employee-performance-wps',
                    'display_name': '有赞员工业绩与WPS日报',
                    'display_name_en': 'Employee Performance and WPS Report',
                    'description': '从有赞订单CSV核算每日员工业绩并同步WPS日报。',
                    'description_zh': '按归属员工核算业绩、高客单、分数及订单数，支持个人WPS授权同步。',
                    'description_en': 'Calculate daily employee performance from Youzan CSV exports and sync to an authorized WPS workbook.',
                    'version': '1.0.0',
                    'author': 'ZhangRulei',
                }
                header = '\n'.join(key + ': ' + json.dumps(value, ensure_ascii=False) for key, value in metadata.items())
                content = ('---\n' + header + '\n---\n\n' + body).encode('utf-8')
            entry = zipfile.ZipInfo('employee-performance-wps/' + relative, date_time=(2026, 11, 6, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(FILES)
    print('公开WorkBuddy包已生成：' + str(destination))


if __name__ == '__main__':
    main()
