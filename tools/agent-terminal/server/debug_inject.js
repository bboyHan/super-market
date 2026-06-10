(function(){
const B='http://localhost:8800/api/capture/ingest';
const F=window.fetch;let n=0;
// 记录所有 fetch 请求看 web_save 有没有走过
window.fetch=async function(...a){
const u=typeof a[0]==='string'?a[0]:a[0]?.url||'';
const i=a[1]||{};
console.log('[DEBUG] fetch:', u.slice(0,120));
if(u.includes('web_save')){
console.log('[DEBUG] *** WEB_SAVE FOUND ***');
const rb=i.body||'';
const r=await F.apply(this,a);
if(r.ok){
const t=await r.clone().text();
console.log('[DEBUG] web_save response:', t.slice(0,200));
const p='weixin://wxpay/bizpayurl?pr=';
const idx=t.indexOf(p);
if(idx>=0){
n++;
let end=idx+80;
for(let j=idx;j<idx+80;j++){const c=t[j];if(c===' '||c===','){end=j;break}}
const url=t.substring(idx,end);
const o=(rb.match(/openid=([A-F0-9]+)/)||[])[1]||'';
fetch(B,{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({type:'payment_url',value:url,source:'web_save',openid:o,body:rb.slice(0,3000)})}).catch(function(){})
} else {
console.log('[DEBUG] weixin URL NOT FOUND in response');
}}
return r}
return F.apply(this,a)}
console.log('[CAP] ready');
// 也检查页面中是否有 iframe
document.querySelectorAll('iframe').forEach(function(f,i){
console.log('[DEBUG] iframe#'+i+':', f.src||'(dynamic)');
});
})();
