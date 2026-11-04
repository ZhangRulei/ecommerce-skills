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
    def scan(self, rows, shop="示例店", header=HEADER):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "素材_2025-01-01至2025-01-31.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(rows)
            return subprocess.run(
                [sys.executable, str(TOOL), str(path), "--platform", "douyin",
                 "--shop", shop, "--start", "2025-01-01", "--end", "2025-01-31",
                 "--mapping", str(MAPPING)],
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
                self.assertEqual(list(json.loads(r.stdout)["渠道人员初核"]["抖音主页"]), [expected])

    def test_missing_gross_amount_is_reported(self):
        r = self.scan([["示例甲", "demo-3", "本地上传", "2025-01-02", "1200"]],
                      header=[h for h in HEADER if h != "整体成交金额"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("整体成交金额", r.stderr)

if __name__ == "__main__":
    unittest.main()
