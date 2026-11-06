import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
// 本夹具验证明细更新与保护逻辑；日报公式、样式在真实WPS工作簿中回读验证。
const code=(await fs.readFile(new URL('wps-performance-sync.js',import.meta.url),'utf8')).replace('result.report=renderDailyReport(sheet);','result.report={verified:true};');
function fixture(initial=[[null,null,null,null,null,null]]){
 const values=structuredClone(initial);
 const sheet={Name:'Sheet1',get UsedRange(){return {Row:1,Rows:{Count:values.length}};},Range(address){
  const match=/^([A-G])(\d+)(?::([A-G])(\d+))?$/.exec(address);if(!match)throw Error('Unsupported range '+address);
  const single=!match[3],c1=match[1].charCodeAt(0)-65,r1=Number(match[2])-1,c2=single?c1:match[3].charCodeAt(0)-65,r2=single?r1:Number(match[4])-1;
  return {get Value2(){if(single)return values[r1]?.[c1]??null;return Array.from({length:r2-r1+1},(_,i)=>Array.from({length:c2-c1+1},(_,j)=>values[r1+i]?.[c1+j]??null));},set Value2(matrix){for(let i=r1;i<=r2;i++){values[i]??=[null,null,null,null,null,null];for(let j=c1;j<=c2;j++)values[i][j]=single?matrix:matrix[i-r1][j-c1];}},set NumberFormat(v){}};
 }};
 const app={Sheets:{Item(name){assert.equal(name,'Sheet1');return sheet;}},ActiveWorkbook:{ReadOnly:false}};
 return {values,run(argv){return vm.runInNewContext('(function(){'+code+'})()',{Application:app,Context:{argv},console:{log(){}}});}};
}
const row={date:'2026-01-02',employee:'示例员工SY',performance:100.01,highPerformance:0,points:0,orderCount:18};
const f=fixture();assert.equal(f.run({}).mode,'preview');assert.equal(f.values[0][0],null);assert.equal(f.run({mode:'upsert',records:[row]}).inserts,1);assert.equal(f.run({mode:'upsert',records:[{...row,performance:101.01}]}).updates,1);assert.equal(f.values.length,2);assert.equal(f.values[1][2],101.01);
assert.throws(()=>f.run({mode:'upsert',records:[row,row]}),/重复/);assert.throws(()=>f.run({mode:'upsert',records:[{...row,date:'2026-02-30'}]}),/日期/);assert.throws(()=>fixture([['其他表头']]).run({mode:'upsert',records:[row]}),/表头/);
f.run({mode:'upsert',records:[{...row,highOrderCount:1}]});assert.equal(f.values[1][6],1);assert.throws(()=>f.run({mode:'upsert',records:[{...row,highOrderCount:19}]}),/高客单订单数/);
console.log('通过：预览不写入、首次写入、重复更新、重复输入拒绝、非法日期拒绝、表头保护、高客单订单数写入和边界保护。');
