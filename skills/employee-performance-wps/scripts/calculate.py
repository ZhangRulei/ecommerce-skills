#!/usr/bin/env python3
"""有赞订单CSV -> 员工业绩；仅使用Python标准库。"""
import argparse
import csv
import datetime as dt
import io
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['订单号', '订单状态', '订单创建时间', '全部商品名称', '订单商品总件数', '归属员工', '订单实付金额']
CN = dt.timezone(dt.timedelta(hours=8))


def money(value):
    text = str(value).strip().replace(',', '').replace('￥', '').replace('¥', '')
    if text.endswith('元'):
        text = text[:-1].strip()
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError('订单实付金额无法解析') from exc
    if not number.is_finite() or number < 0 or number != number.quantize(Decimal('0.01')):
        raise ValueError('订单实付金额必须为非负数且最多两位小数')
    return number


def json_money(value):
    result = float(value)
    if Decimal(str(result)) != value:
        raise ValueError('金额超出可安全保留分精度的JSON数值范围')
    return result


def created_day(value):
    text = str(value).strip().replace('/', '-')
    try:
        parsed = dt.datetime.fromisoformat(text.replace(' ', 'T'))
    except ValueError as exc:
        raise ValueError('订单创建时间无法解析') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN)
    return parsed.astimezone(CN).date().isoformat()


def read_orders(path):
    content = Path(path).read_bytes()
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('CSV编码不是UTF-8或GB18030')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    if not reader.fieldnames:
        raise ValueError('CSV没有表头')
    reader.fieldnames = [h.strip().lstrip('\ufeff').strip() for h in reader.fieldnames]
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('规范化后的CSV表头重复')
    missing = sorted(set(REQUIRED) - set(reader.fieldnames))
    if missing:
        raise ValueError('缺少必要列：' + '、'.join(missing))
    rows = []
    for record in reader:
        if None in record:
            raise ValueError('CSV存在超出表头的字段，请检查引号和分隔符')
        if not any(str(v or '').strip() for v in record.values()):
            continue
        rows.append((reader.line_num, {k: str(v or '').strip() for k, v in record.items()}))
    return rows


def calculate(path, day, rules_path=None, synthetic=False):
    day = dt.date.fromisoformat(day).isoformat()
    rules = json.loads(Path(rules_path or ROOT / 'config/rules.json').read_text(encoding='utf-8-sig'))
    mapping = rules['employee_codes']
    mapping_is_example = rules.get('employee_mapping_kind') != 'private'
    unassigned = rules['unassigned_employee']
    employees = list(dict.fromkeys([*mapping.values(), unassigned]))
    pattern = re.compile(r'[-‐‑–—－]\s*(' + '|'.join(map(re.escape, mapping)) + r')(?![A-Za-z])', re.I)
    source = read_orders(path)
    aggregates = {name: {'paid': Decimal(0), 'high': Decimal(0), 'known_points': 0, 'count': 0, 'high_count': 0, 'pending': 0} for name in employees}
    seen = {}
    selected = []
    duplicates = 0
    for line, record in source:
        tid = record['订单号']
        if not tid:
            raise ValueError(f'第{line}行缺少订单号')
        fingerprint = tuple(record[k] for k in REQUIRED)
        if tid in seen:
            if seen[tid] != fingerprint:
                raise ValueError(f'订单号{tid}的核算字段冲突，不能重复累计或任意取一行')
            duplicates += 1
            continue
        seen[tid] = fingerprint
        if created_day(record['订单创建时间']) == day:
            selected.append((line, record))
    if not selected:
        raise ValueError('CSV中没有目标日期的订单，不能据此生成零业绩')
    details, issues = [], []
    source_paid = Decimal(0)
    closed_paid = Decimal(0)
    closed_count = 0
    for line, record in selected:
        tid, owner, products = record['订单号'], record['归属员工'], record['全部商品名称']
        amount = money(record['订单实付金额'])
        source_paid += amount
        closed = any(fragment.casefold() in record['订单状态'].casefold() for fragment in rules['closed_status_fragments'])
        high = any(keyword in products for keyword in rules['high_product_keywords'])
        employee, matched_codes = unassigned, set()
        if owner:
            chunks = [s.strip() for s in re.split('[;；]', owner) if s.strip()]
            chunk_codes = [set(m.upper() for m in pattern.findall(chunk)) for chunk in chunks]
            matched_codes = set().union(*chunk_codes)
            if len(matched_codes) == 1 and all(len(codes) == 1 for codes in chunk_codes):
                employee = mapping[next(iter(matched_codes))]
            elif not closed:
                issues.append({'orderId': tid, 'type': '归属待核', 'reason': '归属员工代码未知或冲突，暂计待归属'})
        elif not closed:
            issues.append({'orderId': tid, 'type': '归属为空', 'reason': '按已确认口径计入待归属'})
        points, pending_reason = 0, ''
        if closed:
            closed_count += 1
            closed_paid += amount
        else:
            try:
                quantity = Decimal(record['订单商品总件数'])
            except InvalidOperation as exc:
                raise ValueError(f'订单{tid}的商品总件数无法解析') from exc
            if not quantity.is_finite() or quantity < 0 or quantity != quantity.to_integral_value():
                raise ValueError(f'订单{tid}的商品总件数不是非负整数')
            if high:
                matches = {rule['points'] for rule in rules['point_rules'] if rule['keyword'] in products and amount == Decimal(rule['paid_yuan'])}
                if quantity != 1 or ';' in products or '；' in products:
                    pending_reason = '高客单订单含多件或多个商品，需商品级实付及计分口径'
                elif len(matches) != 1:
                    pending_reason = '高客单实付未匹配唯一已确认计分档位'
                else:
                    points = next(iter(matches))
                if pending_reason:
                    points = None
                    issues.append({'orderId': tid, 'type': '计分待核', 'reason': pending_reason})
            agg = aggregates[employee]
            agg['paid'] += amount
            agg['high'] += amount if high else Decimal(0)
            agg['count'] += 1
            agg['high_count'] += int(high)
            if points is None:
                agg['pending'] += 1
            else:
                agg['known_points'] += points
        details.append({'sourceRow': line, 'orderId': tid, 'date': day, 'status': record['订单状态'], 'owner': owner, 'employee': employee, 'products': products, 'paid': json_money(amount), 'included': not closed, 'high': high, 'points': points, 'scoringIssue': pending_reason})
    summary = [{'date': day, 'employee': name, 'performance': json_money(a['paid']), 'highPerformance': json_money(a['high']), 'points': None if a['pending'] else a['known_points'], 'knownPoints': a['known_points'], 'orderCount': a['count'], 'highOrderCount': a['high_count'], 'qualityPerformance': None, 'scoringPendingOrders': a['pending']} for name, a in aggregates.items()]
    paid = sum((a['paid'] for a in aggregates.values()), Decimal(0))
    assert paid + closed_paid == source_paid
    assert sum(r['orderCount'] for r in summary) + closed_count == len(selected)
    assert all(a['high'] <= a['paid'] and a['high_count'] <= a['count'] for a in aggregates.values())
    synthetic = synthetic or any(r.get('数据性质') == '虚构示例' for _, r in source)
    result = {'schemaVersion': 1, 'meta': {'date': day, 'timezone': rules['timezone'], 'sourceName': Path(path).name, 'synthetic': synthetic, 'mappingIsExample': mapping_is_example, 'sourceRows': len(source), 'duplicateRowsRemoved': duplicates, 'selectedUniqueOrders': len(selected), 'excludedClosedOrders': closed_count, 'includedOrders': sum(r['orderCount'] for r in summary), 'performance': json_money(paid), 'highPerformance': json_money(sum((a['high'] for a in aggregates.values()), Decimal(0))), 'highOrderCount': sum(r['highOrderCount'] for r in summary), 'scoringPendingOrders': sum(r['scoringPendingOrders'] for r in summary), 'rulesVersion': rules['version']}, 'rows': summary}
    return result, details, issues


def csv_value(value):
    if value is None:
        return ''
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def save_csv(path, headers, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows([[csv_value(value) for value in row] for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--date', default=(dt.datetime.now(CN).date() - dt.timedelta(days=1)).isoformat())
    parser.add_argument('--output', default='out')
    parser.add_argument('--rules')
    parser.add_argument('--synthetic', action='store_true')
    args = parser.parse_args()
    try:
        result, details, issues = calculate(args.input, args.date, args.rules, args.synthetic)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        save_csv(output / '员工业绩.csv', ['日期', '员工', '业绩', '高客单业绩', '分数', '订单数', '高客单订单数'], [[r['date'], r['employee'], f"{r['performance']:.2f}", f"{r['highPerformance']:.2f}", r['points'], r['orderCount'], r['highOrderCount']] for r in result['rows']])
        columns = ['orderId', 'date', 'status', 'owner', 'employee', 'products', 'paid', 'included', 'high', 'points', 'scoringIssue']
        save_csv(output / '订单核对明细.csv', ['订单号', '日期', '订单状态', '归属员工原值', '核算员工', '商品名称', '订单实付金额', '纳入统计', '高客单', '分数', '计分问题'], [[r[k] for k in columns] for r in details])
        save_csv(output / '待核问题.csv', ['订单号', '类型', '原因'], [[r['orderId'], r['type'], r['reason']] for r in issues])
        print(json.dumps({'output': str(output.resolve()), 'meta': result['meta'], 'issues': len(issues)}, ensure_ascii=False))
    except (ValueError, OSError, AssertionError) as exc:
        parser.exit(2, '核算未完成：' + str(exc) + '\n')


if __name__ == '__main__':
    main()
