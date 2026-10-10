export const PAGE = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KYNX Scripts</title>
<style>
:root{--bg:#0e1116;--panel:#161b22;--line:#2a313c;--text:#e6edf3;--dim:#8b949e;--acc:#58a6ff}
@media (prefers-color-scheme: light){:root{--bg:#f6f8fa;--panel:#fff;--line:#d0d7de;--text:#1f2328;--dim:#656d76;--acc:#0969da}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px system-ui,sans-serif;display:flex;flex-direction:column;height:100vh}
header{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line)}
h1{font-size:15px;margin:0 8px 0 0}input,select,button{background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font:inherit}
button{cursor:pointer}button.primary{background:var(--acc);border-color:var(--acc);color:#fff}button:disabled{opacity:.5}
textarea{flex:1;width:100%;border:0;outline:0;resize:none;padding:14px 16px;background:var(--bg);color:var(--text);font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;tab-size:4}
footer{padding:8px 16px;background:var(--panel);border-top:1px solid var(--line);color:var(--dim);display:flex;gap:12px;flex-wrap:wrap}
footer a{color:var(--acc)}#status{margin-left:auto}
</style></head><body>
<header>
  <h1>KYNX Scripts</h1>
  <input id="title" placeholder="Title (optional)" maxlength="80">
  <button class="primary" id="save">Save</button>
  <button id="update" disabled>Update</button>
  <button id="del" disabled>Delete</button>
  <span style="flex:1"></span>
  <input id="openId" placeholder="Open by ID" size="14"><button id="open">Open</button>
</header>
<textarea id="code" spellcheck="false" placeholder="-- write your code here"></textarea>
<footer><span id="links"></span><span id="count"></span><span id="status"></span></footer>
<script>
const $=id=>document.getElementById(id);let cur=null;
const MAX=${"${MAX}"};
const status=t=>{$("status").textContent=t;};
const tokens=()=>{try{return JSON.parse(localStorage.getItem("kynxTokens")||"{}")}catch{return{}}};
const setToken=(id,t)=>{try{const o=tokens();o[id]=t;localStorage.setItem("kynxTokens",JSON.stringify(o))}catch{}};
function show(id){cur=id;const has=!!(id&&tokens()[id]);$("update").disabled=$("del").disabled=!has;
  $("links").innerHTML=id?'<a href="/#'+id+'">share link</a> · <a href="/raw/'+id+'" target="_blank">raw</a>':"";}
async function api(path,opt){const r=await fetch(path,opt);const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.statusText);return j;}
async function load(id){try{const j=await api("/api/scripts/"+encodeURIComponent(id));$("code").value=j.code;$("title").value=j.title||"";show(id);location.hash=id;status("Opened "+id);count();}catch(e){status(e.message)}}
function count(){$("count").textContent=new Blob([$("code").value]).size+" / "+MAX+" bytes";}
$("code").addEventListener("input",count);
$("code").addEventListener("keydown",e=>{if(e.key==="Tab"){e.preventDefault();const t=e.target,s=t.selectionStart;t.setRangeText("\\t",s,t.selectionEnd,"end");count();}
  if((e.ctrlKey||e.metaKey)&&e.key==="s"){e.preventDefault();$("save").click();}});
$("save").onclick=async()=>{try{const j=await api("/api/scripts",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({code:$("code").value,title:$("title").value})});setToken(j.id,j.token);show(j.id);location.hash=j.id;status("Saved as "+j.id);}catch(e){status(e.message)}};
$("update").onclick=async()=>{try{await api("/api/scripts/"+cur,{method:"PUT",headers:{"content-type":"application/json",authorization:"Bearer "+tokens()[cur]},body:JSON.stringify({code:$("code").value,title:$("title").value})});status("Updated "+cur);}catch(e){status(e.message)}};
$("del").onclick=async()=>{if(!confirm("Delete "+cur+"?"))return;try{await api("/api/scripts/"+cur,{method:"DELETE",headers:{authorization:"Bearer "+tokens()[cur]}});status("Deleted "+cur);$("code").value="";show(null);history.replaceState(null,"",location.pathname);count();}catch(e){status(e.message)}};
$("open").onclick=()=>{const v=$("openId").value.trim();if(v)load(v)};
$("openId").addEventListener("keydown",e=>{if(e.key==="Enter")$("open").click()});
if(location.hash.length>1)load(location.hash.slice(1));count();
</script></body></html>`;
