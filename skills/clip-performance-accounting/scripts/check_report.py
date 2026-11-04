"""复核多平台成品报表的五列总计。仅读取已保存的 Excel 计算结果。"""
import argparse
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook
from check_source import text, title_hits

METRICS = ("期间业绩", "创建业绩", "创建数", "有效数", "创建有效数")
PATTERNS = (
    r"(?:\d{1,2}月|本月|当月|本期)业绩(?:\(元\))?",
    r"(?:当月|当期)?创建/上传业绩(?:\(元\))?",
    r"(?:当月|当期)创建素材数(?:\(含无业绩\))?",
    r"有效素材",
    r"(?:当月|当期)创建有效素材",
)

def normalized(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))

def read_table(ws):
    ws.reset_dimensions()
    rows = iter(ws.values)
    for row in rows:
        names = [normalized(x) for x in row]
        found = [[i for i, n in enumerate(names) if re.fullmatch(p, n)] for p in PATTERNS]
        if all(len(hits) == 1 for hits in found):
            return tuple(hits[0] for hits in found), list(rows)
    raise ValueError(f"{ws.title} 找不到唯一的 D–H 对应指标表头")

def values(row, columns, allow_blank=False):
    result = []
    for key, idx in zip(METRICS, columns):
        v = row[idx] if idx < len(row) else None
        if v in (None, ""):
            if not allow_blank:
                raise ValueError(f"合计的“{key}”无数值，请先在表格引擎重算")
            result.append(Decimal(0))
        else:
            try:
                result.append(Decimal(str(v).replace(",", "")))
            except InvalidOperation as e:
                raise ValueError(f"{key} 含无法解析的值 {v!r}") from e
    return result

def assert_equal(reference, actual, label):
    for i, (a,b) in enumerate(zip(reference, actual)):
        tolerance = Decimal("0.005") if i < 2 else Decimal(0)
        if abs(a-b) > tolerance:
            raise ValueError(f"{label}：{METRICS[i]} 对照值 {a}，实际 {b}")

def sum_lines(rows, columns, allow_blank=False):
    result = [Decimal(0)]*len(METRICS)
    for row in rows:
        result = [a+b for a,b in zip(result, values(row, columns, allow_blank))]
    return result

def review_rows(sheet, required):
    sheet.reset_dimensions()
    rows = iter(sheet.values)
    for row in rows:
        names = [normalized(v) for v in row]
        if set(required).issubset(names):
            for values_ in rows:
                yield {name: values_[i] if i < len(values_) else None
                       for i, name in enumerate(names) if name}
            return
    raise ValueError(f"{sheet.title} 缺少多人归属核对字段")


def report_reviews(book):
    sheets = ("人员标签及口径", "素材归属明细", "当月创建素材清单")
    if any(s not in book.sheetnames for s in sheets):
        return {"状态": "未核验，需查看原表的归属明细与人员标签"}
    people = []
    fields = ("剪辑人员", "抖音账号", "视频简称", "已确认别名")
    for r in review_rows(book[sheets[0]], fields):
        if people and not r["剪辑人员"]:
            break
        if r["剪辑人员"] and r["抖音账号"]:
            people.append(dict(zip(("name","douyin","short","alias"), (r[k] for k in fields))))
    if not people:
        return {"状态": "未核验，未找到人员映射"}
    names = {p["name"] for p in people}
    checked, requests = set(), []
    for sheet, shopfield, idfield, manual, only_created in [
            ("素材归属明细","店铺/账号","素材ID","人工确认人员",False),
            ("当月创建素材清单","店铺/来源","素材ID/视频信息","无业绩素材确认人员",True)]:
        fields = ["平台","业绩类别","素材名称","最终归属",shopfield,idfield,manual,"原始表","原表行号","匹配依据"]
        for r in review_rows(book[sheet], fields):
            if r["平台"] != "抖音":
                continue
            who, title, sid = r["最终归属"], text(r["素材名称"]), text(r[idfield])
            key = (r[shopfield], sid, title, r["原始表"], r["原表行号"])
            if key in checked:
                continue
            checked.add(key)
            if r[manual] in names or r["匹配依据"] == "用户已暂缓":
                continue
            if who in names and r["匹配依据"] in ("人工确认","历史人工确认"):
                continue
            method, hits = title_hits("douyin", title, people)
            if len(hits) < 2:
                continue
            amount = next((v for k,v in r.items() if re.fullmatch(r"\d+月业绩金额\(元\)", k)), None)
            requests.append({"平台":"douyin","店铺／账户":r[shopfield],"渠道":r["业绩类别"],
                             "原始表":r["原始表"],"原表行号":r["原表行号"],"素材ID":sid,
                             "作品名称":r["素材名称"],"业绩金额":amount,"仅涉及创建数":only_created,
                             "待确认原因":method+"命中多人","候选人员":list(hits),"命中依据":hits})
    return {"状态":"需向用户询问" if requests else "无新增多人命中",
            "条数":len(requests),"清单":requests}


def check(path):
    workbook = load_workbook(path, data_only=True, read_only=True)
    try:
        mcols, main = read_table(workbook["人员业绩汇总"])
        pcols, platform = read_table(workbook["平台渠道汇总"])
        personal = [r for r in main if len(r)>1 and normalized(r[1]) in ("合计总业绩","已核算小计(主页待填)")]
        totals = [r for r in main if normalized(r[0]).startswith(("全部人员总计","已核算合计"))]
        pt = [i for i,r in enumerate(platform) if normalized(r[0])=="合计"]
        if not personal or len(totals)!=1 or len(pt)!=1:
            raise ValueError("未能唯一定位人员总计或渠道合计，请核对模板小计标签")
        total = values(totals[0],mcols)
        assert_equal(total,sum_lines(personal,mcols),"人员各块与人员总计")
        assert_equal(total,values(platform[pt[0]],pcols),"人员总计与渠道总计")
        channel_rows = [r for r in platform[:pt[0]] if r[0] and r[1] and r[2]]
        assert_equal(total,sum_lines(channel_rows,pcols,allow_blank=True),"渠道明细与总计")
        pending = [i+1 for i,r in enumerate(main) if len(r)>2 and normalized(r[1])=="已核算小计(主页待填)"]
        return {"个人及待确认分块":len(personal),"渠道账户行":len(channel_rows),
                "微信主页有待填分块":len(pending),"抖音人工确认":report_reviews(workbook),
                "总计":{k:str(v.quantize(Decimal(".01") if i<2 else Decimal("1"))) for i,(k,v) in enumerate(zip(METRICS,total))}}
    finally:
        workbook.close()

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workbook",type=Path)
    try:
        print(json.dumps(check(ap.parse_args().workbook),ensure_ascii=False))
    except (KeyError,ValueError,OSError) as e:
        raise SystemExit(str(e))
