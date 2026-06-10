(function(){
const B='http://localhost:8800/api/capture/ingest';
const F=window.fetch;let n=0;
window.fetch=async function(...a){
const u=typeof a[0]==='string'?a[0]:a[0]?.url||'';
const i=a[1]||{};
if(u.includes('/v1/r/')&&u.includes('web_save')){
const rb=i.body||'';
const r=await F.apply(this,a);
if(r.ok){const t=await r.clone().text();
const p='weixin://wxpay/bizpayurl?pr=';
const idx=t.indexOf(p);
if(idx>=0){
n++;
let end=idx+80;
for(let j=idx;j<idx+80;j++){const c=t[j];if(c===' '||c===','){end=j;break}}
const url=t.substring(idx,end);
const o=(rb.match(/openid=([A-F0-9]+)/)||[])[1]||'';
console.log('[CAP] #'+n+' openid='+o.slice(0,8));
fetch(B,{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({type:'payment_url',value:url,
source:'web_save',openid:o,pay_method:'wechat',
body:rb.slice(0,3000)})}).catch(function(){})
}}return r}
return F.apply(this,a)}
console.log('[CAP] ready')
})();
