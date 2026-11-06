import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {run} from './wps_push.mjs';

const testRoot=path.resolve(process.cwd(),'out','test-client');
if(!testRoot.startsWith(path.resolve(process.cwd())+path.sep))throw Error('测试目录必须在当前工作目录内');
await fs.mkdir(testRoot,{recursive:true});
const temp=await fs.mkdtemp(path.join(testRoot,'performance-client-'));
const input=path.join(temp,'result.json');
const sample={schemaVersion:1,meta:{date:'2026-01-02',synthetic:false,mappingIsExample:false,scoringPendingOrders:0,performance:100.01},rows:[{date:'2026-01-02',employee:'示例员工SY',performance:100.01,highPerformance:0,points:0,orderCount:1,highOrderCount:0}]};
const originalFetch=globalThis.fetch;
let calls=0;
process.env.WPS_AIRSCRIPT_TOKEN='SYNTHETIC_TEST_TOKEN_NOT_A_REAL_CREDENTIAL';
process.env.WPS_PERFORMANCE_WEBHOOK='https://www.kdocs.cn/api/v3/ide/file/DEMO_FILE/script/DEMO_SCRIPT/sync_task';
globalThis.fetch=async(url,options)=>{
 calls++;assert.equal(new URL(url).hostname,'www.kdocs.cn');assert.equal(options.redirect,'error');
 const body=JSON.parse(options.body);assert.equal(body.Context.argv.records.length,1);
 return {ok:true,json:async()=>({status:'finished',error:'',data:{result:{mode:body.Context.argv.mode,worksheet:'Sheet1',verified:true,report:{verified:true},inserts:1,updates:0}}})};
};
try{
 await fs.writeFile(input,JSON.stringify(sample));
 await run(['--input',input,'--mode','preview']);assert.equal(calls,1);
 await run(['--input',input,'--mode','upsert']);assert.equal(calls,2);
 await fs.writeFile(input,JSON.stringify({...sample,meta:{...sample.meta,synthetic:true}}));
 await assert.rejects(run(['--input',input,'--mode','upsert']),/虚构示例/);assert.equal(calls,2);
 await fs.writeFile(input,JSON.stringify({...sample,meta:{...sample.meta,mappingIsExample:true}}));
 await assert.rejects(run(['--input',input,'--mode','upsert']),/员工映射/);assert.equal(calls,2);
 await assert.rejects(run(['--input',input,'--mode','rebuild']),/员工映射/);assert.equal(calls,2);
 const {mappingIsExample,...legacyMeta}=sample.meta;
 await fs.writeFile(input,JSON.stringify({...sample,meta:legacyMeta}));
 await assert.rejects(run(['--input',input,'--mode','upsert']),/员工映射/);assert.equal(calls,2);
 await fs.writeFile(input,JSON.stringify({...sample,meta:{...sample.meta,scoringPendingOrders:1}}));
 await assert.rejects(run(['--input',input,'--mode','preview']),/计分待核/);assert.equal(calls,2);
 await fs.writeFile(input,JSON.stringify(sample));
 process.env.WPS_PERFORMANCE_WEBHOOK='https://example.com/collect';
 await assert.rejects(run(['--input',input]),/官方/);assert.equal(calls,2);
 console.log('通过：请求格式、成功回读、示例写入拦截、待核拦截、非WPS地址拦截；没有发出真实网络请求。');
}finally{
 globalThis.fetch=originalFetch;
 if(!path.resolve(temp).startsWith(testRoot+path.sep))throw Error('拒绝清理测试目录以外的路径');
 await fs.rm(temp,{recursive:true,force:true});
}
