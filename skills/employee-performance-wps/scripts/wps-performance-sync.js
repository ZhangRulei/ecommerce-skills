const PERFORMANCE_MEMBERS = ["示例员工SY", "示例员工KX", "示例员工MR", "示例员工ZH", "示例员工WJ", "示例员工CD", "示例员工XY", "示例员工HH", "待归属"];
// 员工业绩同步：固定写入当前文档的 Sheet1，按日期和员工更新。
// 默认 preview 只检查；upsert写入明细并更新截图式日报，rebuild仅更新日报。
function renderDailyReport(source) {
  const members = PERFORMANCE_MEMBERS;
  const metrics = ['个人账号归属业绩汇总', '优质用户账号业绩', '高客单业绩', '高客单分数', '高客单数量', '总计'];
  const sourceLast = Number(source.UsedRange.Row) + Number(source.UsedRange.Rows.Count) - 1;
  const data = source.Range('A1:G' + sourceLast).Value2;
  const rows = data.slice(1).filter(r => r[0] !== null && r[0] !== undefined && r[0] !== '');
  if (!rows.length) return {worksheet:'业绩日报',status:'无已核算日期'};
  const serial = v => typeof v === 'number' ? Math.floor(v) : Date.parse(String(v) + 'T00:00:00Z') / 86400000 + 25569;
  const sourceDates = [...new Set(rows.map(r => serial(r[0])))].sort((a,b) => b-a);
  if (sourceDates.some(d => !Number.isFinite(d))) throw new Error('明细表存在无法识别的日期');
  const colName = n => {let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26);}return s;};
  let report = null;
  for (let i=1;i<=Application.Sheets.Count;i++) if (Application.Sheets.Item(i).Name==='业绩日报') report=Application.Sheets.Item(i);
  const created = !report;
  if (!report) {report=Application.Sheets.Add(source);report.Name='业绩日报';}
  let dates=[];
  if (!created) {
    const currentLast = Number(report.UsedRange.Column)+Number(report.UsedRange.Columns.Count)-1;
    const first=report.Range('A1:B1').Value2[0];
    if(first[0]!=='运营人员'||first[1]!=='日期') throw new Error('业绩日报表头与预期不一致，停止重建');
    if(currentLast>=3){const header=report.Range('C1:'+colName(currentLast)+'1').Value2[0];for(const v of header){if(v===null||v===undefined||v==='')break;const day=serial(v);if(!Number.isFinite(day))throw new Error('日报日期列存在非日期内容');dates.push(day);}}
  }
  if(created){dates=[...new Set([...sourceDates,...Array.from({length:5},(_,i)=>sourceDates[0]-i)])].sort((a,b)=>b-a);}
  else for(const day of sourceDates){if(dates.includes(day))continue;let index=dates.findIndex(d=>d<day);if(index<0)index=dates.length;report.Range(colName(index+3)+'1').EntireColumn.Insert();dates.splice(index,0,day);}
  const finalCol=colName(dates.length+2),lastRow=members.length*7;
  const area=report.Range('A1:'+finalCol+lastRow);
  area.Font.Name='宋体';area.Font.Size=11;area.Font.Bold=false;area.VerticalAlignment=-4108;area.RowHeight=14.25;area.WrapText=false;
  if(created)area.Interior.Color=RGB(255,255,255);
  for(const edge of [7,8,9,10,11,12]){const b=area.Borders.Item(edge);b.LineStyle=1;b.Weight=2;b.Color=RGB(215,220,226);}
  report.Range('A1:A'+lastRow).ColumnWidth=17;
  report.Range('B1:B'+lastRow).ColumnWidth=25;
  report.Range('C1:'+finalCol+lastRow).ColumnWidth=20;
  report.Range('A1:B1').Value2=[['运营人员','日期']];
  report.Range('C1:'+finalCol+'1').Value2=[dates];report.Range('C1:'+finalCol+'1').NumberFormat='yyyy. m. d';report.Range('A1:'+finalCol+'1').HorizontalAlignment=-4131;
  const money='0.00;-0.00;0;@',blankZeroMoney='0.00;-0.00;;@',blankZeroInteger='0;-0;;@';
  for(let i=0;i<members.length;i++){
    const start=2+i*7,end=start+5,spacer=end+1;
    const nameRange=report.Range('A'+start+':A'+end);if(!nameRange.MergeCells)nameRange.Merge();report.Range('A'+start).Value2=members[i];nameRange.HorizontalAlignment=-4108;
    report.Range('B'+start+':B'+end).Value2=metrics.map(m=>[m]);
    report.Range('B'+start+':B'+end).HorizontalAlignment=-4131;
    report.Range('C'+start+':'+finalCol+end).HorizontalAlignment=-4152;
    for(let j=0;j<dates.length;j++){
      const c=colName(j+3),criteria="'Sheet1'!$A$2:$A$"+sourceLast+','+c+'$1,'+"'Sheet1'!$B$2:$B$"+sourceLast+',$A'+start;
      const exists='COUNTIFS('+criteria+')';
      const formula=(column,extraCheck='')=>'=IF('+exists+'=0,"",'+(extraCheck?'IF('+extraCheck+'=0,"",':'')+'SUMIFS(\'Sheet1\'!$'+column+'$2:$'+column+'$'+sourceLast+','+criteria+')'+(extraCheck?')':'')+')';
      report.Range(c+start).Formula=formula('C');
      // 第二行供后续优质账号业绩填写；刷新时保留其已有值或公式。
      report.Range(c+(start+2)).Formula=formula('D');
      report.Range(c+(start+3)).Formula=formula('E');
      report.Range(c+(start+4)).Formula=formula('G','COUNTIFS('+criteria+',\'Sheet1\'!$G$2:$G$'+sourceLast+',"<>")');
      report.Range(c+end).Formula='=IF('+exists+'=0,"",SUM('+c+start+':'+c+(start+1)+'))';
    }
    report.Range('C'+start+':'+finalCol+start).NumberFormat=money;
    report.Range('C'+(start+1)+':'+finalCol+(start+2)).NumberFormat=blankZeroMoney;
    report.Range('C'+(start+3)+':'+finalCol+(start+4)).NumberFormat=blankZeroInteger;
    report.Range('C'+end+':'+finalCol+end).NumberFormat=money;
    report.Range('B'+end+':'+finalCol+end).Interior.Color=RGB(198,224,180);
    report.Range('A'+spacer+':'+finalCol+spacer).RowHeight=14.25;
  }
  report.Range('B1:B'+lastRow).Borders.Item(10).Color=RGB(145,145,145);
  report.Range('B1:B'+lastRow).Borders.Item(10).Weight=2;
  Application.Calculate();
  for(let i=0;i<members.length;i++)for(let j=0;j<dates.length;j++){
    const matches=rows.filter(r=>serial(r[0])===dates[j]&&r[1]===members[i]);if(!matches.length)continue;
    const start=2+i*7,c=colName(j+3);
    for(const[offset,index]of [[0,2],[2,3],[3,4],[4,6]]){
      if(index===6&&matches.every(r=>r[index]===null||r[index]===undefined||r[index]===''))continue;
      const expected=matches.reduce((n,r)=>n+Number(r[index]||0),0),actual=Number(report.Range(c+(start+offset)).Value2);
      if(Math.abs(actual-expected)>0.000001)throw new Error('日报公式核对失败：'+members[i]+' '+c+(start+offset));
    }
  }
  report.Activate();
  report.Range('C2').Select();
  return {worksheet:'业绩日报',employeeCount:members.length,dateColumns:dates.length,latestDate:new Date((dates[0]-25569)*86400000).toISOString().slice(0,10),qualityPerformance:'留空，保留后续人工填写值',highCount:'有效高客单订单数',freezeManagedBy:'WPS网页视图',verified:true};
}
function syncPerformance(input) {
  const headers = ['日期', '员工', '业绩', '高客单业绩', '分数', '订单数'];
  const members = PERFORMANCE_MEMBERS;
  const mode = input.mode || 'preview';
  if (!['preview','upsert','inspect','rebuild'].includes(mode)) throw new Error('mode 仅支持 preview、upsert、inspect 或 rebuild');
  const sheet = Application.Sheets.Item('Sheet1');
  if (!sheet || sheet.Name !== 'Sheet1') throw new Error('找不到目标工作表 Sheet1');
  if (Application.ActiveWorkbook.ReadOnly) throw new Error('目标文档没有编辑权限');
  const lastUsed = Number(sheet.UsedRange.Row) + Number(sheet.UsedRange.Rows.Count) - 1;
  if (!Number.isInteger(lastUsed) || lastUsed < 1 || lastUsed > 10000) throw new Error('工作表使用范围异常，请人工检查');
  const existing = sheet.Range('A1:F' + lastUsed).Value2;
  if (!Array.isArray(existing) || !Array.isArray(existing[0])) throw new Error('未能读取目标区域');
  const blank = v => v === null || v === undefined || v === '';
  const empty = existing.every(row => row.every(blank));
  const headerMatches = headers.every((h, i) => existing[0][i] === h);
  if (!empty && !headerMatches) throw new Error('A1:F1 表头不一致，已停止以避免覆盖其他数据');
  if(mode==='inspect'){
    const result={mode,worksheet:'Sheet1',sheetNames:Array.from({length:Application.Sheets.Count},(_,i)=>Application.Sheets.Item(i+1).Name),source:sheet.Range('A1:G'+lastUsed).Value2};
    if(result.sheetNames.includes('业绩日报')){const report=Application.Sheets.Item('业绩日报');report.Activate();const endCol=Number(report.UsedRange.Column)+Number(report.UsedRange.Columns.Count)-1;let column='';let n=endCol;while(n){n--;column=String.fromCharCode(65+n%26)+column;n=Math.floor(n/26);}result.report={values:report.Range('A1:'+column+(PERFORMANCE_MEMBERS.length*7+1)).Value2,formulas:report.Range('A1:'+column+(PERFORMANCE_MEMBERS.length*7+1)).Formula,freezePanes:Application.ActiveWindow?.FreezePanes,splitColumn:Application.ActiveWindow?.SplitColumn,splitRow:Application.ActiveWindow?.SplitRow,format:{font:report.Range('A2').Font.Name,nameMerged:report.Range('A2').MergeCells,totalFill:report.Range('B7').Interior.Color,columnA:report.Range('A1').ColumnWidth,columnB:report.Range('B1').ColumnWidth,columnC:report.Range('C1').ColumnWidth,rowHeight:report.Range('B2').RowHeight}};}
    return result;
  }
  if(mode==='rebuild')return {mode,worksheet:'Sheet1',report:renderDailyReport(sheet)};
  const highCountHeader=sheet.Range('G1').Value2;
  if(!blank(highCountHeader)&&highCountHeader!=='高客单订单数')throw new Error('明细G列已有其他内容，停止扩展高客单数量');
  function dateKey(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return new Date((Math.floor(value) - 25569) * 86400000).toISOString().slice(0, 10);
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const d = new Date(value + 'T00:00:00Z');
      if (Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === value) return value;
    }
    throw new Error('日期必须是 yyyy-mm-dd 或有效的表格日期');
  }
  const index = new Map();
  let lastData = empty ? 1 : 1;
  if (!empty) for (let i = 1; i < existing.length; i++) {
    const row = existing[i];
    if (row.every(blank)) continue;
    if (blank(row[0]) || blank(row[1])) throw new Error('第' + (i + 1) + '行缺少日期或员工');
    const key = dateKey(row[0]) + '|' + String(row[1]).trim();
    if (index.has(key)) throw new Error('已有重复的日期和员工，请先核对：' + key);
    index.set(key, i + 1);
    lastData = i + 1;
  }
  const records = input.records || [];
  if (!Array.isArray(records) || records.length > 500) throw new Error('records 必须是最多500条的数组');
  if (mode === 'upsert' && records.length === 0) throw new Error('没有待写入的记录');
  const seen = new Set(), operations = [];
  for (const r of records) {
    const day = dateKey(r.date), employee = String(r.employee || '').trim();
    if (!members.includes(employee)) throw new Error('员工不在已确认名单中：' + employee);
    const numbers = [r.performance, r.highPerformance, r.points, r.orderCount];
    if (numbers.some(v => typeof v !== 'number' || !Number.isFinite(v) || v < 0)) throw new Error('金额、分数和订单数必须是非负数');
    if (numbers.slice(0, 2).some(v => Math.abs(v * 100 - Math.round(v * 100)) > 0.000001)) throw new Error('金额最多保留两位小数');
    if (!Number.isInteger(r.points) || !Number.isInteger(r.orderCount)) throw new Error('分数和订单数必须为整数');
    if (r.highPerformance > r.performance) throw new Error('高客单业绩不能大于总业绩');
    if(r.highOrderCount!==undefined&&(!Number.isInteger(r.highOrderCount)||r.highOrderCount<0||r.highOrderCount>r.orderCount))throw new Error('高客单订单数必须是0到订单数之间的整数');
    const key = day + '|' + employee;
    if (seen.has(key)) throw new Error('本次数据包含重复日期和员工：' + key);
    seen.add(key);
    const existed = index.has(key), rowNumber = existed ? index.get(key) : ++lastData;
    if (rowNumber > 10000) throw new Error('超出预设写入范围');
    const serial = Date.parse(day + 'T00:00:00Z') / 86400000 + 25569;
    operations.push({row: rowNumber, action: existed ? 'update' : 'insert', values: [serial, employee, ...numbers], highOrderCount:r.highOrderCount, date: day, employee});
  }
  const result = {mode, worksheet: 'Sheet1', headerReady: headerMatches, existingRecords: index.size, inserts: operations.filter(x => x.action === 'insert').length, updates: operations.filter(x => x.action === 'update').length};
  if (mode === 'preview') return result;
  if (empty) sheet.Range('A1:F1').Value2 = [headers];
  for (const operation of operations) sheet.Range('A' + operation.row + ':F' + operation.row).Value2 = [operation.values];
  sheet.Range('G1').Value2='高客单订单数';
  for(const operation of operations)if(operation.highOrderCount!==undefined)sheet.Range('G'+operation.row).Value2=operation.highOrderCount;
  sheet.Range('A2:A' + lastData).NumberFormat = 'yyyy-mm-dd';
  sheet.Range('C2:D' + lastData).NumberFormat = '#,##0.00';
  sheet.Range('E2:F' + lastData).NumberFormat = '0';
  for (const operation of operations) {
    const actual = sheet.Range('A' + operation.row + ':F' + operation.row).Value2[0];
    if (dateKey(actual[0]) !== operation.date || actual[1] !== operation.employee || actual.slice(2).some((v, i) => Math.abs(Number(v) - operation.values[i + 2]) > 0.000001)) throw new Error('写后核对失败：第' + operation.row + '行');
  }
  result.verified = true;
  result.report=renderDailyReport(sheet);
  return result;
}
const args = typeof Context === 'object' && Context.argv ? Context.argv : {};
const result = syncPerformance(args);
console.log(JSON.stringify(result));
return result;
