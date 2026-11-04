"""Run the public CLI against synthetic inputs, without a real roster or export."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).with_name("check_source.py")
MAPPING = TOOL.parent.parent / "references" / "attribution.example.json"
HEADER = ["素材名称", "素材ID", "素材来源", "素材创建时间", "整体成交金额", "净成交金额"]

class ClipAccountingTest(unittest.TestCase):
    def scan(self, rows, shop="示例店", header=HEADER, mapping=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "素材_2025-01-01至2025-01-31.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(rows)
            config = MAPPING
            if mapping is not None:
                config = Path(folder) / "mapping.json"
                config.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(TOOL), str(path), "--platform", "douyin",
                 "--shop", shop, "--start", "2025-01-01", "--end", "2025-01-31",
                 "--mapping", str(config)],
                capture_output=True, text=True, encoding="utf-8"
            )

    def test_current_period_and_strict_threshold(self):
        rows = [["示例甲主页1", "demo-"+str(i), "本地上传", day, gross, "1"] for i,(day,gross) in enumerate([
            ("2024-12-31", "1200"), ("2025-01-01", "1000"),
            ("2025-01-31", "1000.01"), ("2025-01-15", "0")], start=10)]
        r = self.scan(rows)
        self.assertEqual(r.returncode, 0, r.stderr)
        metrics = json.loads(r.stdout)["渠道人员初核"]["抖音千川"]["剪辑甲"]
        self.assertEqual(metrics, {"期间业绩": "3200.01", "非零素材": 3,
            "创建业绩": "2000.01", "创建数": 3, "有效数": 2, "创建有效数": 1})

    def test_scoped_manual_confirmation(self):
        row = ["合成作品 #示例抖音甲 #示例抖音乙", "demo-001", "抖音号主页素材",
               "2025-01-05", "250", "1"]
        for shop, expected in [("示例店", "剪辑乙"), ("示例分店", "待确认")]:
            with self.subTest(shop=shop):
                r = self.scan([row], shop=shop)
                self.assertEqual(r.returncode, 0, r.stderr)
                result = json.loads(r.stdout)
                self.assertEqual(list(result["渠道人员初核"]["抖音主页"]), [expected])
                review = result["人工确认"]
                if shop == "示例店":
                    self.assertEqual(review["清单"], [])
                else:
                    self.assertEqual(review["状态"], "需向用户询问")
                    self.assertEqual(review["条数"], 1)
                    item = review["清单"][0]
                    self.assertEqual(item["素材ID"], "demo-001")
                    self.assertEqual(item["候选人员"], ["剪辑甲", "剪辑乙"])
                    self.assertEqual(item["命中依据"]["剪辑乙"], ["#示例抖音乙"])

    def test_only_distinct_active_matches_prompt(self):
        titles = ["剪辑甲-示例乙", "示例甲-ja", "示例甲 #示例抖音乙", "无标记",
                  "#示例抖音甲 #示例抖音乙", "#示例抖音甲 #示例抖音乙"]
        rows = [[t, "test-"+str(i), "本地上传", day, amt, "0"]
                for i,(t,day,amt) in enumerate(zip(titles, ["2025-01-02"]*5+["2024-12-31"], [500,200,300,100,0,0]))]
        r = self.scan(rows)
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.loads(r.stdout)
        pending = result["人工确认"]["清单"]
        self.assertEqual([x["素材ID"] for x in pending], ["test-0", "test-4"])
        self.assertEqual(pending[0]["命中依据"], {"剪辑甲":["剪辑甲"],"剪辑乙":["示例乙"]})
        self.assertTrue(pending[1]["仅涉及创建数"])
        self.assertEqual(result["渠道人员初核"]["抖音千川"]["待确认"]["期间业绩"], "600")

    def test_answer_and_explicit_deferral_survive_rerun(self):
        mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
        t = "#示例抖音甲 #示例抖音乙"
        items = [{"id":"test-x","title":t,"owner":"剪辑甲"},
                 {"id":"test-y","title":t,"owner":"暂缓"}]
        mapping["confirmed_materials"] = [mapping["confirmed_materials"], {
            "period":"2025-01", "platform":"抖音", "shop":"示例店", "records":items}]
        rows = [[t, sid, "抖音号主页素材", "2025-01-01", amount, "0"]
                for sid,amount in [("test-x",100),("test-y",200),("test-z",300)]]
        r = self.scan(rows, mapping=mapping)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual([x["素材ID"] for x in data["人工确认"]["清单"]], ["test-z"])
        self.assertEqual(data["渠道人员初核"]["抖音主页"]["剪辑甲"]["期间业绩"], "100")
        self.assertEqual(data["渠道人员初核"]["抖音主页"]["待确认"]["期间业绩"], "500")

    def test_missing_gross_amount_is_reported(self):
        r = self.scan([["示例甲", "demo-3", "本地上传", "2025-01-02", "1200"]],
                      header=[h for h in HEADER if h != "整体成交金额"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("整体成交金额", r.stderr)

    def test_workbook_audit_flags_unreviewed_rows_once(self):
        from io import BytesIO
        try:
            import openpyxl
        except ImportError:
            self.skipTest("XLSX 检查需要 openpyxl")
        from check_report import report_reviews
        w = openpyxl.Workbook()
        people = w.active
        people.title = "人员标签及口径"
        people.append(["剪辑人员","抖音账号","视频简称","已确认别名"])
        people.append(["剪辑甲","示例抖音甲","-ja",None])
        people.append(["剪辑乙","示例抖音乙","-jb",None])
        detail = w.create_sheet("素材归属明细")
        created = w.create_sheet("当月创建素材清单")
        first = ["平台","业绩类别","素材名称","最终归属"]
        last = ["原始表","原表行号","匹配依据"]
        detail.append(first+["店铺／账号","素材ID","人工确认人员"]+last+["10月业绩金额（元）"])
        created.append(first+["店铺／来源","素材ID／视频信息","无业绩素材确认人员"]+last)
        for i,owner in enumerate([None,"剪辑甲"],1):
            row = ["抖音","抖音主页","#示例抖音甲 #示例抖音乙",owner or "待确认",
                   "示例店",str(i),owner,"底表",i,"话题命中多人"]
            detail.append(row+[150])
            created.append(row)
        buffer = BytesIO(); w.save(buffer); buffer.seek(0)
        rb = openpyxl.load_workbook(buffer,read_only=True,data_only=True)
        try:
            result = report_reviews(rb)
        finally:
            rb.close()
        self.assertEqual(result["条数"],1)
        self.assertEqual(result["清单"][0]["候选人员"],["剪辑甲","剪辑乙"])
        self.assertEqual(result["清单"][0]["业绩金额"],150)

if __name__ == "__main__":
    unittest.main()
