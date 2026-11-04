"""只读核对一份平台导出。可选输出行级底稿，不写入输入文件。"""
import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

# 名称列、素材键、业绩列、创建时间、来源列
FIELDS = {
    "douyin": ("素材名称", "素材ID", "整体成交金额", "素材创建时间", "素材来源"),
    "wechat-ads": ("素材名称", "视频信息", "成交订单金额(元)", "上传时间", None),
    "wechat-home": ("短视频名", None, "成交金额", None, None),
    "kuaishou": ("视频名称", "视频ID", "当日总成交订单金额", "创建时间", "视频来源"),
    "adq": ("名称", "视频ID", "净成交订单金额", "创建时间", None),
}
CHANNELS = {
    "douyin": {"抖音号主页素材": "抖音主页", "抖音主页素材": "抖音主页", "本地上传": "抖音千川",
               "-": "抖音千川", "AIGC动态创意": None, "全部": None},
    "kuaishou": {"个人主页": "快手主页", "本地上传": "磁力金牛", "小店上传": "磁力金牛",
                 "AI修复": "磁力金牛", "快创/高光片段": "磁力金牛"},
}
DEFAULT_CHANNEL = {"wechat-ads": "微信小店", "wechat-home": "微信主页", "adq": "ADQ"}
TOPIC_FIELD = {"douyin": "douyin", "wechat-ads": "wechat", "kuaishou": "kuaishou"}
BLANK = {"", "-", "--"}

def text(value):
    return unicodedata.normalize("NFKC", str(value if value is not None else "")).replace("\ufeff", "").strip()

def records(path, sheet):
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=True)
        try:
            if not sheet and len(book.sheetnames) != 1:
                raise ValueError("多工作表文件请用 --sheet 指定原始数据表")
            ws = book[sheet] if sheet else book.worksheets[0]
            ws.reset_dimensions()
            yield from ws.values
        finally:
            book.close()
    elif path.suffix.lower() == ".csv":
        raw = path.read_bytes()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        else:
            try:
                raw.decode("utf-8-sig")
                encoding = "utf-8-sig"
            except UnicodeDecodeError:
                encoding = "gb18030"
        with path.open(encoding=encoding, newline="") as handle:
            yield from csv.reader(handle)
    else:
        raise ValueError("支持原始 .xlsx 或 .csv 导出")

def source_period(filename):
    dates = re.findall(r"(?<!\d)20\d{2}-\d{2}-\d{2}(?!\d)", filename)
    if len(dates) == 2:
        return tuple(date.fromisoformat(x) for x in dates)
    compact = re.search(r"(?<!\d)(20\d{6})\s*[-至]\s*(20\d{6})(?!\d)", filename)
    if compact:
        return tuple(datetime.strptime(s, "%Y%m%d").date() for s in compact.groups())
    return None

def num(value):
    v = text(value)
    if v in BLANK:
        return None
    try:
        result = Decimal(v.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"非法金额 {v!r}") from exc
    if not result.is_finite():
        raise ValueError(f"非法金额 {v!r}")
    return result

def created_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if text(value) in BLANK:
        return None
    if isinstance(value, (float, int)):
        from openpyxl.utils.datetime import from_excel
        result = from_excel(value)
        if isinstance(result, datetime):
            return result.date()
    v = text(value).replace("/", "-").split(" ")[0].split("T")[0]
    return datetime.strptime(v, "%Y-%m-%d").date()

def channel(platform, source):
    if platform in CHANNELS:
        choices = CHANNELS[platform]
        if source not in choices:
            raise ValueError(f"未定义的素材来源 {source!r}，需核实分类")
        return choices[source]
    return DEFAULT_CHANNEL[platform]

def resolve(platform, shop, title, material, start, end, mapping):
    people = mapping["people"]
    if platform == "wechat-home":
        alias = mapping.get("wechat_home_aliases", {}).get(shop, shop)
        matches = [p["name"] for p in people if text(p["wechat"]).casefold() == text(alias).casefold()]
        if len(matches) == 1:
            return matches[0], "视频号账号映射", alias
        return "待确认", "账号未唯一匹配", alias
    t = text(title)
    prior = mapping.get("confirmed_materials")
    if (prior and platform == "douyin" and prior.get("platform") in ("抖音", "douyin")
            and shop in [prior["shop"], *prior.get("shop_aliases", [])]
            and start.strftime("%Y-%m") == end.strftime("%Y-%m") == prior["period"]):
        same = next((v for v in prior["records"] if v["id"] == material), None)
        if same:
            if " ".join(t.split()) != " ".join(text(same["title"]).split()):
                return "待确认", "原确认ID相同但标题不同", material
            return same["owner"], "历史人工确认", material
    hits = {}
    for p in people:
        labels = [p["name"], *(p.get("alias") or "").split("、")]
        found = [s for s in labels if s and s in t]
        if p.get("short") and re.search(re.escape(p["short"]) + r"(?![A-Za-z])", t, re.I):
            found.append(p["short"])
        if found:
            hits[p["name"]] = "、".join(found)
    unknown = [s for s in mapping.get("unconfirmed", []) if s and
               (re.search(r"(?:^|[-_ (])" + re.escape(s), t) if len(s) == 1 else s in t)]
    evidence = "；".join(f"{name}={v}" for name, v in hits.items())
    if unknown:
        return "待确认", "人员关系待确认", "；".join(x for x in [evidence, "、".join(unknown)] if x)
    if len(hits) == 1:
        return next(iter(hits)), "姓名或简称", evidence
    if hits:
        return "待确认", "姓名或简称命中多人", evidence
    tags = {s.casefold() for s in re.findall(r"#([^\s#，,。.!！?？、；;：:\[\]【】]+)", t)}
    field = TOPIC_FIELD.get(platform)
    candidates = [p for p in people if field and text(p.get(field)).casefold() in tags]
    if len(candidates) == 1:
        return candidates[0]["name"], "账号话题", candidates[0][field]
    return "待确认", "话题命中多人" if candidates else "未匹配", "、".join(p["name"] for p in candidates)

def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--platform", required=True, choices=FIELDS)
    parser.add_argument("--shop", required=True, help="实际店铺、广告账户，或微信主页视频号名称")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="统计末日（含）")
    parser.add_argument("--verified-period", action="store_true", help="已从文件名以外的证据确认统计期")
    parser.add_argument("--sheet")
    parser.add_argument("--mapping", type=Path, required=True, help="本地人员账号、别名及人工确认映射 JSON")
    parser.add_argument("--detail-csv", type=Path, help="新文件，保存非零或期内创建行；主页保留原表行")
    return parser.parse_args()

def run(a):
    if a.end < a.start:
        raise ValueError("统计结束日早于开始日")
    period = source_period(a.file.name)
    if period and period != (a.start, a.end):
        raise ValueError(f"导出期间 {period} 与请求不符")
    if not period and not a.verified_period:
        raise ValueError("文件名不能证明统计区间；核实导出面板或已确认范围后再加 --verified-period")
    title, ident, field, stamp, src = FIELDS[a.platform]
    config = json.loads(a.mapping.read_text(encoding="utf-8-sig"))
    tally = Counter()
    detail = []
    grouped = {}
    seen = {}
    required = {s for s in [title, ident, field, stamp, src] if s}
    it = enumerate(records(a.file, a.sheet), 1)
    for line, row in it:
        cols = [text(v) for v in row]
        if title in cols and (ident or field) in cols:
            if any(cols.count(v) != 1 for v in required):
                raise ValueError(f"金额或必需列缺失／不唯一。必需 {sorted(required)}，实际 {cols}")
            ix = {v: i for i,v in enumerate(cols)}
            break
        if line >= 30:
            raise ValueError(f"前 30 行内未找到预期表头 {title!r}；检查文件和工作表")
    else:
        raise ValueError("找不到原始表头")
    for line, row in it:
        if not any(v is not None and text(v) != "" for v in row):
            continue
        def get(name):
            return row[ix[name]] if name and ix[name] < len(row) else None
        tally["原始行"] += 1
        try:
            if a.platform == "adq" and "所属账户" in ix:
                account = text(get("所属账户"))
                if account and account != text(a.shop):
                    raise ValueError(f"所属账户 {account!r} 与 --shop 不符，需要拆分来源")
            cat = channel(a.platform, text(get(src)))
            if not cat:
                tally["剔除来源"] += 1
                continue
            amount = num(get(field))
            creation = created_date(get(stamp)) if stamp else None
            item = get(ident)
            if isinstance(item, (int,float)) and abs(item) >= 10**15:
                raise ValueError("长ID为数值存储，需要原始文本ID")
            item_id = text(item)
            if ident and item_id not in BLANK:
                if item_id in seen:
                    raise ValueError(f"素材键重复，前一行为 {seen[item_id]}。请核重复导出或数据粒度")
                seen[item_id] = line
            elif ident:
                tally["缺少素材键"] += 1
        except (ValueError,TypeError,OverflowError) as exc:
            raise ValueError(f"{a.file.name} 第 {line} 行：{exc}") from exc
        nonzero = amount is not None and amount != 0
        if not nonzero:
            tally["金额空白" if amount is None else "金额为零"] += 1
        if stamp and creation is None:
            tally["缺少创建时间"] += 1
        inside = creation is not None and a.start <= creation < a.end + timedelta(days=1)
        if not (nonzero or inside or a.platform == "wechat-home"):
            continue
        owner, method, evidence = resolve(a.platform,a.shop,get(title),item_id,a.start,a.end,config)
        metrics = grouped.setdefault(cat, {}).setdefault(owner, Counter())
        if a.platform == "wechat-home":
            metrics["主页E参考额"] += amount or Decimal(0)
        else:
            effective = amount is not None and amount > 1000
            metrics["期间业绩"] += amount or Decimal(0)
            metrics["非零素材"] += int(nonzero)
            metrics["创建业绩"] += (amount or Decimal(0)) if inside else Decimal(0)
            metrics["创建数"] += int(inside)
            metrics["有效数"] += int(effective)
            metrics["创建有效数"] += int(effective and inside)
        detail.append([a.file.name, a.sheet or "", line, a.platform, a.shop, cat, item_id,
                       get(title), field, amount, creation, owner, method, evidence])
    if a.detail_csv:
        with a.detail_csv.open("x", encoding="utf-8-sig", newline="") as out:
            writer=csv.writer(out)
            writer.writerow(["源文件","指定工作表","原表行号","平台","店铺账户","类别","素材键","素材名称","金额字段","业绩金额","创建日期","初核人员","判定方式","依据"])
            writer.writerows(detail)
    return {"文件":str(a.file),"期间":[str(a.start),str(a.end)],"金额字段":field,
            "原表计数":dict(tally),"渠道人员初核":grouped}

if __name__ == "__main__":
    try:
        print(json.dumps(run(arguments()),ensure_ascii=False,default=str))
    except (ValueError,KeyError,OSError) as error:
        raise SystemExit(str(error))
