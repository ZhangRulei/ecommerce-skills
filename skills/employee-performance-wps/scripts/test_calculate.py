#!/usr/bin/env python3
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEST_TMP=(Path.cwd()/'out'/'test-temp').resolve()
if not TEST_TMP.is_relative_to(Path.cwd().resolve()):
    raise RuntimeError('测试临时目录必须位于当前工作目录内')
TEST_TMP.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('calculator',Path(__file__).with_name('calculate.py'))
calculator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator)


class CalculationTests(unittest.TestCase):
    def sample(self):
        return calculator.calculate(ROOT/'examples/demo_orders.csv','2026-01-02')

    def custom(self,updates=None,extra=None):
        with (ROOT/'examples/demo_orders.csv').open(encoding='utf-8-sig',newline='') as file:
            reader=csv.DictReader(file);headers=reader.fieldnames;rows=list(reader)
        if updates:rows[0].update(updates)
        if extra:rows.append(extra)
        # 将重复行保持为同样内容，单独检验其他边界。
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            path=Path(tmp)/'orders.csv'
            with path.open('w',encoding='utf-8-sig',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=headers);writer.writeheader();writer.writerows(rows)
            return calculator.calculate(path,'2026-01-02')

    def test_amount_count_points_and_dedup(self):
        result,_,issues=self.sample()
        self.assertEqual(result['meta']['includedOrders'],5)
        self.assertEqual(result['meta']['excludedClosedOrders'],1)
        self.assertEqual(result['meta']['duplicateRowsRemoved'],1)
        self.assertEqual(result['meta']['performance'],3349.95)
        self.assertEqual(result['meta']['highPerformance'],3199.97)
        self.assertEqual(result['meta']['highOrderCount'],3)
        self.assertEqual(sum(r['points'] for r in result['rows']),10)
        self.assertEqual(len(result['rows']),9)
        self.assertTrue(result['meta']['synthetic'])
        self.assertTrue(result['meta']['mappingIsExample'])
        self.assertEqual(next(r for r in result['rows'] if r['employee']=='待归属')['performance'],49.99)
        self.assertEqual(len(issues),1)

    def test_no_target_date_is_not_zero(self):
        with self.assertRaisesRegex(ValueError,'没有目标日期'):
            calculator.calculate(ROOT/'examples/demo_orders.csv','2026-01-03')

    def test_private_mapping_and_script_use_same_names(self):
        rules=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
        rules['employee_mapping_kind']='private'
        rules['employee_codes']['SY']='本机测试员工'
        helper_spec=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('prepare_wps_script.py'))
        helper=importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            private=Path(tmp)/'private-rules.json'
            private.write_text(json.dumps(rules,ensure_ascii=False),encoding='utf-8')
            result,_,_=calculator.calculate(ROOT/'examples/demo_orders.csv','2026-01-02',private)
            self.assertFalse(result['meta']['mappingIsExample'])
            self.assertEqual(next(r for r in result['rows'] if r['employee']=='本机测试员工')['points'],2)
            output=helper.prepare(private,Path(tmp)/'wps.js')
            member_line=next(line for line in output.read_text(encoding='utf-8').splitlines() if line.startswith('const PERFORMANCE_MEMBERS = '))
            self.assertEqual(json.loads(member_line.removeprefix('const PERFORMANCE_MEMBERS = ').removesuffix(';')),[*rules['employee_codes'].values(),'待归属'])
            with self.assertRaisesRegex(ValueError,'不能覆盖'):
                helper.prepare(private,ROOT/'scripts/wps-performance-sync.js')

    def test_conflicting_duplicate_is_rejected(self):
        extra={'订单号':'DEMO001','订单状态':'待发货','订单创建时间':'2026-01-02 09:00:00','全部商品名称':'青春演示套组','订单商品总件数':'1','归属员工':'演示-SY','订单实付金额':'1.00','数据性质':'虚构示例'}
        with self.assertRaisesRegex(ValueError,'冲突'):
            self.custom(extra=extra)

    def test_unknown_owner_is_unassigned(self):
        result,_,issues=self.custom({'归属员工':'未知-ZZ'})
        self.assertEqual(next(r for r in result['rows'] if r['employee']=='待归属')['orderCount'],2)
        self.assertTrue(any(r['type']=='归属待核' for r in issues))

    def test_multi_item_score_is_unavailable(self):
        result,_,issues=self.custom({'订单商品总件数':'2','订单实付金额':'1399.98'})
        row=next(r for r in result['rows'] if r['employee']=='示例员工SY')
        self.assertIsNone(row['points'])
        self.assertEqual(row['performance'],1399.98)
        self.assertEqual(result['meta']['scoringPendingOrders'],1)
        self.assertTrue(any(r['type']=='计分待核' for r in issues))

    def test_unknown_high_price_is_unavailable(self):
        result,_,_=self.custom({'订单实付金额':'688.00'})
        self.assertIsNone(next(r for r in result['rows'] if r['employee']=='示例员工SY')['points'])

    def test_invalid_money_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'实付金额'):
            self.custom({'订单实付金额':'错误金额'})

    def test_whitespace_headers(self):
        text=(ROOT/'examples/demo_orders.csv').read_text(encoding='utf-8-sig').replace('归属员工',' 归属员工 ')
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            path=Path(tmp)/'space.csv';path.write_text(text,encoding='utf-8-sig')
            result,_,_=calculator.calculate(path,'2026-01-02')
            self.assertEqual(result['meta']['performance'],3349.95)


if __name__=='__main__':
    unittest.main()
