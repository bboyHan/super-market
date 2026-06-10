/**
 * CDP 注入工具 — Node.js 版（WebSocket）
 *
 * 用法: node cdp_inject.js [页面标题关键词]
 * 环境变量: CDP_PORT=9222  BACKEND_URL=http://127.0.0.1:8800
 */

const http = require('http');
const WebSocket = require('ws');

const CDP_PORT = process.env.CDP_PORT || 9222;
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8800';
const KEYWORD = process.argv[2] || '王者';

// ── 拦截脚本 ────────────────────────────────

const SCRIPT = `
(function(){
if(window.__CDP_DONE)return;
window.__CDP_DONE=true;
window.__CDP_PAYURL='';
var XS=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send=function(b){
var u=this._url||'';
if(u.indexOf('web_save')>=0||u.indexOf('CommonCall')>=0||u.indexOf('wechat_query')>=0||u.indexOf('create_order')>=0){
var x=this;var rb=typeof b==='string'?b:'';
x.addEventListener('load',function(){
try{
var t=x.responseText;
window.__CDP_LAST=t.slice(0,3000);
var i=t.indexOf('weixin://wxpay/bizpayurl?pr=');
if(i>=0){window.__CDP_PAYURL=t.substring(i,i+80).split('"')[0].split(' ')[0].split(')')[0];}
}catch(e){}});
}
return XS.apply(this,arguments)};
console.log('[OK]');
})();
`;

// ── CDP 通信 ────────────────────────────────

let msgId = 0;
function cdpSend(ws, method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise(resolve => {
    const handler = data => {
      const msg = JSON.parse(data.toString());
      if (msg.id === id) resolve(msg);
    };
    ws.on('message', handler);
    // 超时
    setTimeout(() => { ws.removeListener('message', handler); resolve(null); }, 5000);
  });
}

async function main() {
  // 1. 获取页面列表
  const pages = await new Promise((resolve, reject) => {
    http.get(`http://localhost:${CDP_PORT}/json`, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve(JSON.parse(d)));
    }).on('error', reject);
  });

  // 2. 找目标页面
  let target = null;
  for (const p of pages) {
    const url = p.url || '';
    if (url.includes(KEYWORD) || url.includes('pay.qq.com')) { target = p; break; }
  }
  if (!target) target = pages.find(p => !p.url.includes('chrome-extension') && p.url.startsWith('http'));
  if (!target) { console.error('无可用页面'); process.exit(1); }

  const pageId = target.id;
  const wsUrl = `ws://127.0.0.1:${CDP_PORT}/devtools/page/${pageId}`;
  console.log(`[CDP] 页面: ${target.title}`);
  console.log(`[CDP] URL: ${(target.url||'').slice(0,80)}`);

  // 3. WebSocket 连接
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => {
    ws.on('open', resolve);
    ws.on('error', reject);
    setTimeout(() => reject(new Error('WS超时')), 5000);
  });

  console.log('[CDP] WebSocket 已连接');

  // 4. 注入脚本
  const injectResult = await cdpSend(ws, 'Runtime.evaluate', {
    expression: SCRIPT, awaitPromise: false
  });

  const err = injectResult?.result?.exceptionDetails;
  if (err) {
    console.error('[CDP] 注入失败:', err.text || JSON.stringify(err));
    process.exit(1);
  }
  console.log('[CDP] ✅ 脚本已注入');
  console.log('[CDP] 现在操作支付，自动轮询...');

  // 5. 轮询捕获
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000));

    const r = await cdpSend(ws, 'Runtime.evaluate', {
      expression: 'window.__CDP_PAYURL || ""'
    });
    const payUrl = r?.result?.result?.value || '';

    if (payUrl) {
      console.log(`\n🎯 捕获到支付URL!`);
      console.log(`   ${payUrl}`);

      // 存工具端
      const body = JSON.stringify({ type: 'payment_url', value: payUrl, source: 'cdp_node' });
      const req = http.request(`${BACKEND}/api/capture/ingest`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
      });
      req.write(body); req.end();
      console.log('✅ 已存入数据库');

      // 也输出 last response
      const r2 = await cdpSend(ws, 'Runtime.evaluate', {
        expression: 'window.__CDP_LAST ? window.__CDP_LAST.slice(0,300) : ""'
      });
      const lastResp = r2?.result?.result?.value || '';
      if (lastResp) console.log('  响应内容:', lastResp.slice(0,200));

      ws.close();
      process.exit(0);
    }

    // 显示请求计数
    const r3 = await cdpSend(ws, 'Runtime.evaluate', {
      expression: 'window.__CDP_DONE === true ? "ready" : "no"'
    });
    const ready = r3?.result?.result?.value || '';
    process.stdout.write(`\r[${i+1}/60] ${ready === 'ready' ? '⏳' : '⏳'}`);
  }

  console.log('\n[CDP] 超时');
  ws.close();
  process.exit(1);
}

main().catch(e => {
  console.error('\n[CDP] 错误:', e.message);
  process.exit(1);
});
