#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export async function run(argv=process.argv.slice(2)) {
  const options={mode:'preview'};
  for(let i=0;i<argv.length;i+=2){if(!['--input','--mode','--receipt'].includes(argv[i])||argv[i+1]===undefined)throw Error('参数仅支持--input、--mode、--receipt');options[argv[i].slice(2)]=argv[i+1];}
  if(!options.input)throw Error('必须通过--input指定计算器输出的result.json');
  if(!['preview','upsert','inspect','rebuild'].includes(options.mode))throw Error('mode须为preview、upsert、inspect或rebuild');
  const input=JSON.parse((await fs.readFile(options.input,'utf8')).replace(/^\uFEFF/,''));
  if(input.schemaVersion!==1||!Array.isArray(input.rows)||!input.meta)throw Error('输入不是本技能的核算结果');
  if(input.meta.synthetic&&options.mode!=='preview'&&options.mode!=='inspect')throw Error('虚构示例禁止写入或重建真实WPS工作簿，请改用真实订单结果');
  if(['upsert','rebuild'].includes(options.mode)&&input.meta.mappingIsExample!==false)throw Error('员工映射仍为示例或未经标记；请使用本机private-rules.json重新核算后同步');
  if(input.meta.scoringPendingOrders>0||input.rows.some(r=>r.points===null))throw Error('存在计分待核订单，请先补充口径，不上传不确定分数');
  const seen=new Set();
  for(const r of input.rows){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||typeof r.employee!=='string'||!r.employee)throw Error('日期或员工字段无效');
    const key=r.date+'|'+r.employee;if(seen.has(key))throw Error('输入包含重复日期和员工');seen.add(key);
    if([r.performance,r.highPerformance,r.points,r.orderCount,r.highOrderCount].some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0))throw Error('输入指标含无效数值');
    if(!Number.isInteger(r.points)||!Number.isInteger(r.orderCount)||!Number.isInteger(r.highOrderCount)||r.highOrderCount>r.orderCount||r.highPerformance>r.performance)throw Error('输入计数或金额关系不正确');
  }
  const webhook=process.env.WPS_PERFORMANCE_WEBHOOK,token=process.env.WPS_AIRSCRIPT_TOKEN;
  if(!webhook||!token)throw Error('请在本机credentials.local.env填写本人Webhook和脚本令牌');
  const url=new URL(webhook);
  if(url.protocol!=='https:'||url.hostname!=='www.kdocs.cn'||!/^\/api\/v3\/ide\/file\/[^/]+\/script\/[^/]+\/sync_task$/.test(url.pathname)||url.search||url.hash)throw Error('Webhook不是WPS官方同步执行脚本地址');
  const records=input.rows.map(({date,employee,performance,highPerformance,points,orderCount,highOrderCount})=>({date,employee,performance,highPerformance,points,orderCount,highOrderCount}));
  const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','AirScript-Token':token},body:JSON.stringify({Context:{argv:{mode:options.mode,records},sheet_name:'Sheet1'}}),signal:AbortSignal.timeout(45000),redirect:'error'});
  if(!response.ok)throw Error('WPS调用未完成，HTTP '+response.status+'；请检查权限或网络，不要输出令牌');
  const body=await response.json();
  if(body.status!=='finished'||body.error){
    const safe=JSON.stringify({status:body.status,error:body.error,logs:(body.data?.logs??[]).filter(r=>r.level==='error')}).split(token).join('[凭据已隐藏]').split(webhook).join('[Webhook]');
    throw Error('WPS脚本未成功：'+safe.slice(0,1200));
  }
  const result=body.data?.result;
  if(!result||result.worksheet!=='Sheet1'||result.mode!==options.mode)throw Error('WPS返回内容不符合本技能的同步脚本');
  if(options.mode==='upsert'&&(!result.verified||!result.report?.verified))throw Error('写后回读未通过，请先inspect核对，不要报告成功');
  if(options.mode==='rebuild'&&!result.report?.verified)throw Error('日报刷新未通过核对');
  const receipt={checkedAt:new Date().toISOString(),mode:options.mode,date:input.meta.date,records:records.length,performance:input.meta.performance,result};
  const receiptPath=options.receipt||path.join(path.dirname(path.resolve(options.input)),'wps-'+options.mode+'-receipt.json');
  await fs.writeFile(receiptPath,JSON.stringify(receipt,null,2));
  console.log(JSON.stringify({mode:options.mode,records:records.length,receipt:receiptPath,result:options.mode==='inspect'?{worksheet:result.worksheet,sheetNames:result.sheetNames,sourceRows:result.source?.length}:result}));
  return receipt;
}

if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(fileURLToPath(import.meta.url))){
  run().catch(error=>{console.error(error instanceof TypeError?'WPS网络连接未完成，未输出请求凭据':error.message);process.exitCode=1;});
}
