import unittest
from decimal import Decimal as D
from calculate_weekly import calculate


class WeeklyRules(unittest.TestCase):
    def test_douyin_single_unit_and_unpaid_closed(self):
        rows=[{'子订单编号':'a','订单提交时间':'2026-10-01','支付完成时间':'2026-10-01','订单状态':'已关闭','商品单价':'100','商品数量':2,'订单应付金额':180},
              {'子订单编号':'b','订单提交时间':'2026-10-01','支付完成时间':'-','订单状态':'已关闭','商品单价':50}]
        x=calculate(rows,'douyin','2026-10',cutoff='2026-10-18')
        self.assertEqual((x['total']['gmv'],x['total']['paid'],x['total']['refund']),(D(150),D(100),D(100)))
        self.assertEqual([(w['start'],w['end']) for w in x['weeks']],[('2026-09-28','2026-10-04'),('2026-10-05','2026-10-11'),('2026-10-12','2026-10-18')])

    def test_cross_month_payment(self):
        x=calculate([{'子订单编号':'a','订单提交时间':'2026-09-30','支付完成时间':'2026-10-01','订单状态':'已关闭','商品单价':100}],'douyin','2026-09')
        self.assertEqual(x['total']['gmv'],100)
        self.assertEqual(x['total']['paid'],0)
        self.assertEqual(x['weeks'][-1]['paid'],100)
        self.assertEqual((x['weeks'][-1]['start'],x['weeks'][-1]['end']),('2026-09-28','2026-10-04'))
        self.assertEqual(x['full_week_range_total']['paid'],100)

    def test_cross_month_full_weeks_and_separate_month_total(self):
        rows=[{'订单号':str(i),'订单创建时间':day,'订单支付时间':day,'订单状态':'交易关闭','实付款':amount}
              for i,(day,amount) in enumerate([('2026-09-28',10),('2026-09-30',20),('2026-10-01',30),('2026-10-04',40),('2026-10-31',50),('2026-11-01',60)])]
        x=calculate(rows,'kuaishou','2026-10',coverage_start='2026-09-28',coverage_end='2026-11-01')
        self.assertEqual(x['weeks'][0]['paid'],100)
        self.assertEqual(x['weeks'][-1]['paid'],110)
        self.assertEqual(x['total']['paid'],120)
        self.assertEqual(x['full_week_range_total']['paid'],210)
        self.assertEqual(sum(w['paid'] for w in x['weeks']),x['full_week_range_total']['paid'])
        self.assertTrue(all(w['coverage_status']=='confirmed' for w in x['weeks']))

    def test_missing_cross_month_source_marked(self):
        row={'订单号':'a','订单创建时间':'2026-10-01','订单支付时间':'2026-10-01','订单状态':'交易关闭','实付款':30}
        x=calculate([row],'kuaishou','2026-10',cutoff='2026-10-18',coverage_start='2026-10-01',coverage_end='2026-10-18')
        self.assertEqual(x['weeks'][0]['coverage_status'],'incomplete_source')
        self.assertEqual(x['weeks'][0]['missing_source_dates'],['2026-09-28','2026-09-29','2026-09-30'])
        self.assertEqual(x['weeks'][0]['paid'],30)

    def test_cutoff_does_not_truncate_week_label(self):
        rows=[{'订单号':str(i),'订单创建时间':day,'订单支付时间':day,'订单状态':'交易关闭','实付款':10}
              for i,day in enumerate(['2026-10-13','2026-10-14'])]
        x=calculate(rows,'kuaishou','2026-10',cutoff='2026-10-13')
        self.assertEqual((x['weeks'][-1]['start'],x['weeks'][-1]['end']),('2026-10-12','2026-10-18'))
        self.assertEqual(x['weeks'][-1]['coverage_status'],'incomplete_cutoff')
        self.assertEqual(x['weeks'][-1]['paid'],10)
        self.assertEqual(len(x['weeks'][-1]['excluded_after_cutoff']),5)

    def test_year_boundary_and_leap_year(self):
        x=calculate([],'kuaishou','2027-01')
        self.assertEqual(x['weeks'][0]['start'],'2026-12-28')
        self.assertEqual(x['weeks'][0]['end'],'2027-01-03')
        leap=calculate([],'kuaishou','2028-02')
        self.assertEqual(leap['weeks'][-1]['end'],'2028-03-05')
        self.assertEqual(leap['month_total_end'],'2028-02-29')

    def test_kuaishou_state_not_notes(self):
        rows=[{'订单号':'a','订单创建时间':'2026-10-12','订单支付时间':'2026-10-12','订单状态':'交易关闭','售后状态':'退款成功','实付款':'¥99.99','订单备注':'已退款5元'},
              {'订单号':'b','订单创建时间':'2026-10-12','订单支付时间':'2026-10-12','订单状态':'交易成功','售后状态':'退款成功','实付款':50}]
        x=calculate(rows,'kuaishou','2026-10')
        self.assertEqual(x['total']['paid'],D('149.99'))
        self.assertEqual(x['total']['refund'],D('99.99'))

    def test_wechat_no_dedup_same_receipt_field(self):
        row={'订单号':'a','订单下单时间':'2026-10-12','支付时间':'2026-10-12','订单状态':'已取消','订单实际收款金额':100,'订单实际支付金额':80,'商品已退款金额':5}
        x=calculate([row,row],'wechat','2026-10')
        self.assertEqual(x['total']['paid'],200)
        self.assertEqual(x['total']['refund'],200)
        self.assertEqual(x['duplicate_id_rows'],1)

    def test_pdd_paid_next_day_and_unpaid_gmv(self):
        rows=[{'订单号':'261018-a','订单成交时间':'2026-10-19 12:02:37','订单状态':'已发货，待收货','售后状态':'无售后或售后取消','商家实收金额(元)':99.99},
              {'订单号':'261018-b','订单成交时间':'','订单状态':'已取消','售后状态':'无售后','商家实收金额(元)':50},
              {'订单号':'261018-c','订单成交时间':'2026-10-18','订单状态':'已收货，退款成功','售后状态':'退款成功','商家实收金额(元)':100,'用户实付金额(元)':80,'商家备注':'已退20'}]
        x=calculate(rows,'pinduoduo','2026-10',cutoff='2026-10-18')
        self.assertEqual(x['weeks'][-1]['gmv'],D('249.99'))
        self.assertEqual(x['weeks'][-1]['paid'],D('199.99'))
        self.assertEqual(x['weeks'][-1]['refund'],100)

    def test_youzan_partial_success_and_in_progress(self):
        base={'订单创建时间':'2026-09-01','买家付款时间':'2026-09-01','订单状态':'交易完成','订单实付金额':100,'订单已退款金额':5}
        x=calculate([dict(base,订单号='a',订单退款状态='退款成功（部分退款）'),dict(base,订单号='b',订单退款状态='退款中')],'youzan','2026-09')
        self.assertEqual(x['total']['paid'],200)
        self.assertEqual(x['total']['refund'],100)

    def test_blank_costs_and_zero_payment_ratio(self):
        x=calculate([],'kuaishou','2026-10')
        for k in ['refund_rate','short_video_spend','live_adq_spend','total_spend','net_roi','gross_roi','spend_rate']:
            self.assertIsNone(x['total'][k])

    def test_invalid_date_fails(self):
        with self.assertRaises(ValueError):
            calculate([{'订单号':'a','订单创建时间':'2026-10-01','订单支付时间':'未知','订单状态':'交易关闭','实付款':10}],'kuaishou','2026-10')


if __name__=='__main__':
    unittest.main()
