"""One-shop weekly sales calculator. Reads original-header CSV/JSON; stdlib only."""
import argparse
import calendar
import csv
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

CONFIG = {
    'douyin': ('商品单价', '订单提交时间', '支付完成时间', '子订单编号'),
    'kuaishou': ('实付款', '订单创建时间', '订单支付时间', '订单号'),
    'wechat': ('订单实际收款金额', '订单下单时间', '支付时间', '订单号'),
    'pinduoduo': ('商家实收金额(元)', None, '订单成交时间', '订单号'),
    'youzan': ('订单实付金额', '订单创建时间', '买家付款时间', '订单号'),
}
BLANK_TIME = {'', '-', '--', '0'}
DATE_RE = re.compile(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?$')


def clean(value):
    return '' if value is None else str(value).strip()


def normalize(row):
    result = {}
    for key, value in row.items():
        label = clean(key).lstrip('\ufeff')
        if label in result:
            raise ValueError('清理空白后存在重复表头：' + label)
        result[label] = value
    return result


def parse_date(value):
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise ValueError('请先把带时区日期规范为业务当地时间')
        return value.date()
    if isinstance(value, date):
        return value
    text = clean(value)
    if text in BLANK_TIME:
        return None
    match = DATE_RE.fullmatch(text)
    if not match:
        raise ValueError('无法解析日期，请先规范为YYYY-MM-DD或当地日期时间：' + text)
    y, m, d, hh, mm, ss = match.groups()
    return datetime(int(y), int(m), int(d), int(hh or 0), int(mm or 0), int(ss or 0)).date()


def parse_money(value):
    text = clean(value).replace(',', '').replace('¥', '').replace('￥', '').strip()
    if not text:
        raise ValueError('金额为空，需核实源数据，不能静默当作0')
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError('金额格式不正确：' + text) from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('非有限值或负数金额需单独核实：' + text)
    return amount


def is_refund(platform, row):
    status = clean(row['订单状态'])
    if platform == 'douyin':
        return status == '已关闭'
    if platform == 'kuaishou':
        return status == '交易关闭'
    if platform == 'wechat':
        return status == '已取消'
    if platform == 'pinduoduo':
        return '退款成功' in status or clean(row['售后状态']) == '退款成功'
    return clean(row['订单退款状态']) in {'退款成功（全额退款）', '退款成功（部分退款）'}


def empty_bucket():
    return {'order_rows': 0, 'gmv': Decimal(0), 'paid_rows': 0,
            'paid': Decimal(0), 'refund_rows': 0, 'refund': Decimal(0)}


def finish(bucket):
    result = dict(bucket)
    result['net'] = bucket['paid'] - bucket['refund']
    result['refund_rate'] = bucket['refund'] / bucket['paid'] if bucket['paid'] else None
    # No historical or default-zero advertising values.
    result.update({key: None for key in ('short_video_spend', 'live_adq_spend',
                                       'total_spend', 'net_roi', 'gross_roi', 'spend_rate')})
    return result


def calculate(records, platform, month, shop='', cutoff=None, coverage_start=None, coverage_end=None):
    if platform not in CONFIG:
        raise ValueError('不支持的平台：' + platform)
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('月份必须为YYYY-MM')
    year, number = map(int, month.split('-'))
    first = date(year, number, 1)
    month_end = date(year, number, calendar.monthrange(year, number)[1])
    last = parse_date(cutoff) if cutoff else month_end
    if last is None or not first <= last <= month_end:
        raise ValueError('截止日必须在指定月份内')
    week_first = first - timedelta(days=first.weekday())
    week_last = last + timedelta(days=6-last.weekday())
    data_end = last if cutoff else week_last
    if (coverage_start is None) != (coverage_end is None):
        raise ValueError('来源覆盖起止日期必须同时提供')
    covered_first = parse_date(coverage_start) if coverage_start is not None else None
    covered_last = parse_date(coverage_end) if coverage_end is not None else None
    if coverage_start is not None and (covered_first is None or covered_last is None or covered_first > covered_last):
        raise ValueError('来源覆盖日期无效')
    field, created_field, paid_field, id_field = CONFIG[platform]
    required = {field, paid_field, id_field, '订单状态'}
    if created_field:
        required.add(created_field)
    if platform == 'pinduoduo':
        required.add('售后状态')
    if platform == 'youzan':
        required.add('订单退款状态')
    buckets = {}
    current = week_first
    while current <= week_last:
        buckets[current] = empty_bucket()
        current += timedelta(days=1)
    identifiers = Counter()
    issues = []
    rows = 0
    observed_dates = set()
    for ordinal, raw in enumerate(records, 2):
        row = normalize(raw)
        if not any(clean(v) for v in row.values()):
            continue
        rows += 1
        source_row = row.get('原行号', row.get('原表行号', ordinal))
        missing = required - row.keys()
        if missing:
            raise ValueError(f'原表行{source_row}缺字段：{sorted(missing)}')
        oid = clean(row[id_field])
        if not oid:
            raise ValueError(f'原表行{source_row}订单编号为空')
        identifiers[oid] += 1
        try:
            amount = parse_money(row[field])
            paid_date = parse_date(row[paid_field])
            if platform == 'pinduoduo':
                match = re.fullmatch(r'(\d{2})(\d{2})(\d{2})-.+', oid)
                if not match:
                    raise ValueError('拼多多订单号不是已确认的YYMMDD-…格式')
                yy, mm, dd = map(int, match.groups())
                created = date(2000 + yy, mm, dd)
                payment_bucket = created if paid_date else None
            else:
                created = parse_date(row[created_field])
                payment_bucket = paid_date
        except ValueError as exc:
            raise ValueError(f'原表行{source_row}：{exc}') from exc
        observed_dates.update(day for day in (created, payment_bucket) if day is not None)
        if created in buckets and created <= data_end:
            buckets[created]['order_rows'] += 1
            buckets[created]['gmv'] += amount
        else:
            issues.append({'source_row': source_row, 'order_id': oid,
                           'metric': 'gmv', 'reason': 'missing_date' if created is None else 'outside_period',
                           'date': created.isoformat() if created else None, 'amount': amount})
        if paid_date is not None:
            if payment_bucket in buckets and payment_bucket <= data_end:
                bucket = buckets[payment_bucket]
                bucket['paid_rows'] += 1
                bucket['paid'] += amount
                if is_refund(platform, row):
                    bucket['refund_rows'] += 1
                    bucket['refund'] += amount
            else:
                issues.append({'source_row': source_row, 'order_id': oid, 'metric': 'paid',
                               'reason': 'outside_period', 'date': payment_bucket.isoformat(), 'amount': amount})
    def aggregate(start, end):
        result = empty_bucket()
        for day, bucket in buckets.items():
            if start <= day <= end:
                for key in result:
                    result[key] += bucket[key]
        return finish(result)
    weeks = []
    current = week_first
    while current <= week_last:
        end = current + timedelta(days=6)
        excluded_after_cutoff = [day.isoformat() for day in buckets if current <= day <= end and day > data_end]
        missing_source_dates = ([day.isoformat() for day in buckets if current <= day <= end and not covered_first <= day <= covered_last]
                                if covered_first is not None else None)
        status = ('incomplete_cutoff' if excluded_after_cutoff else
                  'source_coverage_unconfirmed' if covered_first is None else
                  'incomplete_source' if missing_source_dates else 'confirmed')
        weeks.append({'start': current.isoformat(), 'end': end.isoformat(),
                      'coverage_status': status, 'missing_source_dates': missing_source_dates,
                      'excluded_after_cutoff': excluded_after_cutoff, **aggregate(current, end)})
        current = end + timedelta(days=1)
    return {'platform': platform, 'shop': shop, 'month': month, 'cutoff': data_end.isoformat(),
            'month_total_start': first.isoformat(), 'month_total_end': last.isoformat(),
            'weekly_range_start': week_first.isoformat(), 'weekly_range_end': week_last.isoformat(),
            'coverage_start': covered_first.isoformat() if covered_first else None,
            'coverage_end': covered_last.isoformat() if covered_last else None,
            'observed_date_min': min(observed_dates).isoformat() if observed_dates else None,
            'observed_date_max': max(observed_dates).isoformat() if observed_dates else None,
            'amount_field': field, 'source_rows': rows, 'duplicate_id_rows': sum(v-1 for v in identifiers.values()),
            'daily': [{'date': day.isoformat(), **finish(bucket)} for day, bucket in buckets.items()],
            'weeks': weeks, 'total': aggregate(first, last),
            'full_week_range_total': aggregate(week_first, week_last), 'date_exceptions': issues}


def load_records(path, encoding):
    if path.suffix.lower() == '.json':
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, list) or any(not isinstance(r, dict) for r in value):
            raise ValueError('JSON须为原表头记录对象数组')
        return value
    if path.suffix.lower() == '.csv':
        with path.open(encoding=encoding, newline='') as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            if len(headers) != len(set(clean(h).lstrip('\ufeff') for h in headers)):
                raise ValueError('CSV表头重复，需先核实')
            return list(reader)
    raise ValueError('仅支持CSV或JSON；Excel先只读提取原表头记录')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=CONFIG, required=True)
    parser.add_argument('--month', required=True)
    parser.add_argument('--shop', default='')
    parser.add_argument('--cutoff', help='实际统计截止日；周标签仍至周日并标注未完整。默认覆盖与该月相交的完整自然周')
    parser.add_argument('--coverage-start', help='经核实的来源覆盖起日；不可仅由首笔订单猜测')
    parser.add_argument('--coverage-end', help='经核实的来源覆盖止日；应与coverage-start同时提供')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--encoding', default='utf-8-sig')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('输出不能覆盖输入文件')
    result = calculate(load_records(args.input, args.encoding), args.platform, args.month, args.shop, args.cutoff,
                       args.coverage_start, args.coverage_end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'source_rows': result['source_rows'], 'week_count': len(result['weeks']),
                      'total': result['total']}, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
