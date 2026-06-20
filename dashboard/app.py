"""Local dashboard: upload a voiceover (+ optional script) -> synced doodle MP4.

Run:  python -m dashboard.app   then open http://localhost:5000
Needs OPENAI_API_KEY in the environment (transcription + images).
"""
from __future__ import annotations
import os, json, threading, uuid, re, pathlib
from flask import Flask, request, jsonify, render_template_string, send_file, abort

try:  # load .env so keys (ElevenLabs, OpenAI, YouTube) are picked up automatically
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).parent.parent / ".env")
except Exception:  # python-dotenv is optional; shell env still works
    pass

from pipeline.doodle.builder import build_project, NeedImages
from pipeline.doodle import script_writer, voiceover, thumbnail, youtube_upload

ROOT = pathlib.Path(__file__).parent.parent
PROJECTS = ROOT / "projects"
app = Flask(__name__)
JOBS: dict[str, dict] = {}


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "video"


def _read_meta(d: pathlib.Path) -> dict:
    p = d / "metadata.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - tolerate a hand-edited file
            pass
    return {}


def _write_meta(d: pathlib.Path, meta: dict) -> None:
    (d / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Doodle Studio</title>
<style>
 :root{--bg:#0e0e12;--card:#17171d;--line:#2a2a33;--txt:#e9e9ee;--mut:#9a9aa6;
       --accent:#7c5cff;--accent2:#f5c542;--ok:#34d399}
 *{box-sizing:border-box}
 body{font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--txt);margin:0}
 .app{display:flex;min-height:100vh}
 .side{width:250px;flex:0 0 250px;border-right:1px solid var(--line);background:#121217;
       padding:20px 14px;height:100vh;position:sticky;top:0;overflow-y:auto}
 .brand{font-size:18px;font-weight:800;padding:4px 8px 14px}
 .newbtn{width:100%;margin-bottom:14px}
 .plist{display:flex;flex-direction:column;gap:2px}
 .pitem{display:block;width:100%;text-align:left;background:transparent;color:var(--txt);
        border:0;border-radius:8px;padding:9px 10px;font:inherit;font-weight:600;cursor:pointer}
 .pitem:hover{background:#1e1e26;opacity:1} .pitem.active{background:#26262f}
 .pitem small{display:block;color:var(--mut);font-weight:400;font-size:12px;margin-top:1px}
 .main{flex:1;max-width:760px;padding:40px 28px}
 audio{width:100%;margin-top:8px}
 h1{font-size:26px;margin:0 0 4px} .sub{color:var(--mut);margin:0 0 24px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px}
 label{display:block;font-weight:600;margin:18px 0 6px;font-size:14px}
 form>label:first-child{margin-top:0}
 input[type=text],textarea{width:100%;padding:11px 12px;background:#0f0f14;
      border:1px solid var(--line);border-radius:10px;color:var(--txt);font:inherit}
 input:focus,textarea:focus{outline:none;border-color:var(--accent)}
 textarea{height:140px;resize:vertical}
 input[type=file]{color:var(--mut);font-size:14px}
 input[type=file]::file-selector-button{background:#26262f;color:var(--txt);border:1px solid var(--line);
      border-radius:8px;padding:8px 12px;margin-right:10px;cursor:pointer}
 .row{display:flex;gap:8px}
 button{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:12px 20px;
      font:inherit;font-weight:700;cursor:pointer;transition:opacity .2s} button:hover{opacity:.9}
 button:disabled{opacity:.45;cursor:default}
 #gen{background:#26262f;border:1px solid var(--line);white-space:nowrap}
 .primary{width:100%;margin-top:24px;padding:14px;font-size:16px}
 .titles{color:var(--mut);font-size:13px;white-space:pre-wrap;margin-top:8px}
 #status{margin-top:22px;display:none}
 .stat{display:flex;align-items:center;gap:12px}
 .spin{width:20px;height:20px;border:3px solid var(--line);border-top-color:var(--accent);
      border-radius:50%;animation:sp 1s linear infinite;flex:0 0 auto}
 @keyframes sp{to{transform:rotate(360deg)}}
 .stage{font-weight:700} .detail{color:var(--mut);font-size:14px;margin-top:2px}
 .bar{height:8px;background:#0f0f14;border:1px solid var(--line);border-radius:6px;overflow:hidden;margin-top:14px}
 .bar>div{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .4s}
 video{width:100%;margin-top:18px;border-radius:12px;border:1px solid var(--line)}
 .done{margin-top:16px;padding:16px;background:#0f1a14;border:1px solid #1f5c43;border-radius:12px}
 .dl{display:inline-block;background:var(--ok);color:#04140d;font-weight:700;text-decoration:none;
      padding:11px 18px;border-radius:10px}
 .path{color:var(--mut);font-size:13px;margin-top:10px;word-break:break-all}
 .err{color:#fca5a5}
 .est{color:var(--accent2);font-size:13px;margin-top:12px}
</style></head><body>
<div class="app">
<aside class="side">
  <div class="brand">🎬 Doodle Studio</div>
  <button class="newbtn" id="newBtn">＋ New Video</button>
  <div class="plist" id="plist"></div>
</aside>
<main class="main">
<div id="builder">
<h1>New Video</h1>
<p class="sub">Write a script with Claude, drop in your ElevenLabs voiceover, get a synced doodle video.</p>
<div class="card">
<form id="f">
  <label>Project name</label>
  <input type="text" name="name" placeholder="why-cities-never-sleep" required>
  <label>Script <span style="color:var(--mut);font-weight:400">(optional — timing comes from the audio)</span></label>
  <div class="row">
    <input type="text" id="topic" placeholder="Topic, e.g. What actually is tax?">
    <button type="button" id="gen">✨ Write with Claude</button>
  </div>
  <textarea name="script" id="script" placeholder="Paste a script, or generate one above. Copy it into ElevenLabs to make your voiceover."></textarea>
  <div class="titles" id="titles"></div>
  <button type="button" id="meta" style="margin-top:14px;background:#26262f;border:1px solid var(--line)">📝 Generate description + tags</button>
  <div id="metaout"></div>
  <label>Pace — seconds per image <span id="spiVal" style="color:var(--accent2);font-weight:700"></span>
    <span style="color:var(--mut);font-weight:400">(lower = more images, more cost; higher = fewer)</span></label>
  <input type="range" name="seconds_per_image" id="spi" min="2" max="12" step="1"
         style="width:100%;accent-color:var(--accent)">
  <label>Voiceover</label>
  <div id="voGenRow" class="row" style="display:none">
    <button type="button" id="voBtn" style="background:#26262f;border:1px solid var(--line)">🎙 Generate voiceover</button>
  </div>
  <div class="est" id="voNote"></div>
  <div id="voStatus" style="display:none;margin-top:10px">
    <div class="stat"><div class="spin" id="voSpin"></div>
      <div><div class="stage" id="voStage">Narrating…</div><div class="detail" id="voDetail"></div></div></div>
  </div>
  <div id="voPlayer"></div>
  <label style="margin-top:14px;font-weight:400;color:var(--mut)" id="voUploadLabel">…or upload your own (mp3 / m4a / wav)</label>
  <input type="file" name="audio" accept="audio/*">
  <div class="est" id="est"></div>
  <button type="submit" class="primary">Generate Video</button>
</form>
<div id="status">
  <div class="stat"><div class="spin" id="spin"></div>
    <div><div class="stage" id="stage">Starting…</div><div class="detail" id="detail"></div></div></div>
  <div class="bar"><div id="fill"></div></div>
  <div id="result"></div>
</div>
</div>
</div>
<div id="projview" style="display:none"></div>
</main>
</div>
<script>
const gen=document.getElementById('gen'), topic=document.getElementById('topic'),
      scriptBox=document.getElementById('script'), titles=document.getElementById('titles');
gen.onclick=async()=>{
  if(!topic.value.trim()){topic.focus();return;}
  gen.disabled=true; const old=gen.textContent; gen.textContent='Writing… (~30s)'; titles.textContent='';
  try{
    const r=await fetch('/script',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({topic:topic.value.trim()})});
    const j=await r.json();
    if(j.error){titles.innerHTML='<span class="err">Error: '+j.error+'</span>';}
    else{scriptBox.value=j.script; titles.textContent=j.extras||'';}
  }catch(e){titles.innerHTML='<span class="err">Error: '+e+'</span>';}
  gen.disabled=false; gen.textContent=old;
};
const f=document.getElementById('f'), s=document.getElementById('status'),
      stage=document.getElementById('stage'), fill=document.getElementById('fill'),
      detail=document.getElementById('detail'), result=document.getElementById('result'),
      spin=document.getElementById('spin'), btn=f.querySelector('.primary');
f.onsubmit=async e=>{
  e.preventDefault(); btn.disabled=true; s.style.display='block'; result.innerHTML='';
  spin.style.display='block'; stage.textContent='Uploading…'; detail.textContent=''; fill.style.width='5%';
  const r=await fetch('/build',{method:'POST',body:new FormData(f)});
  const j=await r.json();
  if(j.error){spin.style.display='none'; stage.textContent='Error';
    detail.innerHTML='<span class="err">'+j.error+'</span>'; btn.disabled=false; return;}
  poll(j.job);
};
function poll(job){
  const names={transcribe:'Transcribing voiceover',segments:'Planning scenes',images:'Drawing doodles',
               assemble:'Assembling video',done:'Done',queued:'Queued'};
  const t=setInterval(async()=>{
    const j=await (await fetch('/status/'+job)).json();
    stage.textContent=names[j.stage]||j.stage; detail.textContent=j.detail||'';
    let m=(j.detail||'').match(/(\\d+)\\/(\\d+)/);
    if(j.stage==='images'&&m){fill.style.width=(10+80*m[1]/m[2])+'%';}
    else if(j.stage==='transcribe'){fill.style.width='8%';}
    else if(j.stage==='segments'){fill.style.width='10%';}
    else if(j.stage==='assemble'){fill.style.width='92%';}
    if(j.done){
      clearInterval(t); btn.disabled=false; spin.style.display='none';
      if(j.error){stage.textContent='Error'; detail.innerHTML='<span class="err">'+j.error+'</span>';}
      else{fill.style.width='100%'; stage.textContent='Done ✅'; detail.textContent='';
        result.innerHTML='<video controls src="/video/'+j.project+'?v='+Date.now()+'"></video>'+
          '<div class="done"><a class="dl" href="/video/'+j.project+'?dl=1">⬇ Download MP4 for YouTube</a>'+
          (j.video_path?'<div class="path">Saved at: '+j.video_path+'</div>':'')+'</div>';
        loadProjects(j.project);}
    }
  },1500);
}
// --- generate description + tags with Claude (subscription, free) ---
const meta=document.getElementById('meta'), metaout=document.getElementById('metaout');
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function field(label,val,h){return '<label style="margin-top:14px">'+label+
  ' <span style="color:var(--mut);font-weight:400">(click to select)</span></label>'+
  '<textarea readonly style="height:'+h+'px" onclick="this.select()">'+esc(val)+'</textarea>';}
meta.onclick=async()=>{
  const tp=topic.value.trim()||document.querySelector('input[name=name]').value.trim();
  if(!tp){topic.focus();return;}
  meta.disabled=true; const o=meta.textContent; meta.textContent='Generating… (~30s)';
  metaout.innerHTML='';
  try{
    const r=await fetch('/metadata',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({topic:tp,script:scriptBox.value})});
    const j=await r.json();
    if(j.error){metaout.innerHTML='<div class="titles err">'+esc(j.error)+'</div>';}
    else{metaout.innerHTML=field('Title',j.title,46)+field('Description',j.description,180)+field('Tags',j.tags,80);}
  }catch(e){metaout.innerHTML='<div class="titles err">'+esc(''+e)+'</div>';}
  meta.disabled=false; meta.textContent=o;
};
// --- generate the voiceover with ElevenLabs (uses your EL quota) ---
const voBtn=document.getElementById('voBtn'), voNote=document.getElementById('voNote'),
      voStatus=document.getElementById('voStatus'), voStage=document.getElementById('voStage'),
      voDetail=document.getElementById('voDetail'), voSpin=document.getElementById('voSpin'),
      voPlayer=document.getElementById('voPlayer'), voGenRow=document.getElementById('voGenRow'),
      nameInput=document.querySelector('input[name=name]');
let ttsOn=false;
function voNoteUpdate(){
  if(!ttsOn){voNote.textContent=''; return;}
  const chars=(scriptBox.value||'').replace(/\\s+/g,' ').trim().length;
  voNote.textContent = chars ? 'ElevenLabs will use ~'+chars.toLocaleString()+
    ' characters of your voice quota for this script.' : '';
}
scriptBox.addEventListener('input', voNoteUpdate);
voBtn.onclick=async()=>{
  const name=(nameInput.value||'').trim();
  if(!name){nameInput.focus(); return;}
  if(!scriptBox.value.trim()){scriptBox.focus(); return;}
  voBtn.disabled=true; voPlayer.innerHTML=''; voStatus.style.display='block';
  voSpin.style.display='block'; voStage.textContent='Narrating…'; voDetail.textContent='';
  let j;
  try{
    j=await (await fetch('/voiceover',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name, script:scriptBox.value})})).json();
  }catch(e){j={error:''+e};}
  if(j.error){voStage.textContent='Error'; voSpin.style.display='none';
    voDetail.innerHTML='<span class="err">'+esc(j.error)+'</span>'; voBtn.disabled=false; return;}
  const t=setInterval(async()=>{
    const s=await (await fetch('/status/'+j.job)).json();
    voDetail.textContent=s.detail||'';
    if(s.done){
      clearInterval(t); voBtn.disabled=false; voSpin.style.display='none';
      if(s.error){voStage.textContent='Error'; voDetail.innerHTML='<span class="err">'+esc(s.error)+'</span>';}
      else{voStage.textContent='Voiceover ready ✅'; voDetail.textContent='You can now Generate Video.';
        voPlayer.innerHTML='<audio controls src="/audio/'+name+'?v='+Date.now()+'"></audio>';
        loadProjects(name);}
    }
  },1200);
};
// --- live cost estimate (no API call; reads audio length in the browser) ---
let CFG={seconds_per_image:8,quality:'low'}, audioDur=0;
const PRICE={low:0.02,medium:0.06,high:0.19};
const est=document.getElementById('est'), audioInput=document.querySelector('input[name=audio]');
const spi=document.getElementById('spi'), spiVal=document.getElementById('spiVal');
spi.oninput=()=>{spiVal.textContent=spi.value+'s'; recalc();};
fetch('/config').then(r=>r.json()).then(c=>{CFG=c;
  spi.value=Math.min(12,Math.max(2,Math.round(c.seconds_per_image||4)));
  spiVal.textContent=spi.value+'s'; recalc();
  ttsOn=!!c.tts_available; voGenRow.style.display=ttsOn?'flex':'none'; voNoteUpdate();
  if(!ttsOn){document.getElementById('voUploadLabel').textContent='Voiceover (mp3 / m4a / wav)';}
}).catch(()=>{});
audioInput.onchange=()=>{
  const file=audioInput.files[0]; if(!file){audioDur=0; est.textContent=''; return;}
  const a=document.createElement('audio'); a.preload='metadata';
  a.onloadedmetadata=()=>{audioDur=a.duration||0; recalc(); URL.revokeObjectURL(a.src);};
  a.src=URL.createObjectURL(file);
};
function recalc(){
  if(!audioDur){est.textContent=''; return;}
  const per=parseFloat(spi.value)||CFG.seconds_per_image||8;
  const n=Math.max(1,Math.ceil(audioDur/per));
  const cost=n*(PRICE[CFG.quality]||PRICE.low);
  const mins=(audioDur/60).toFixed(1);
  est.textContent='Estimate: ~'+n+' images for a '+mins+' min video ≈ $'+cost.toFixed(2)+
    ' at '+CFG.quality+' quality (+~$0.01 transcription)';
}
// --- project library sidebar ---
const plist=document.getElementById('plist'), builderView=document.getElementById('builder'),
      detailView=document.getElementById('projview'), newBtn=document.getElementById('newBtn');
async function loadProjects(active){
  let items=[]; try{items=await (await fetch('/projects')).json();}catch(e){}
  plist.innerHTML = items.length ? '' : '<div class="path" style="padding:8px">No projects yet</div>';
  items.forEach(p=>{
    const b=document.createElement('button');
    b.className='pitem'+(p.name===active?' active':'');
    b.innerHTML=esc(p.title)+'<small>'+(p.has_video?'🎬 video ready':'⏳ no video')+'</small>';
    b.onclick=()=>openProject(p.name); plist.appendChild(b);
  });
}
newBtn.onclick=()=>{detailView.style.display='none'; builderView.style.display='block';
  [...plist.children].forEach(c=>c.classList&&c.classList.remove('active'));};
function thumbCard(name,p){
  const n=p.image_count||0;
  const preview = p.has_thumb ?
    '<img id="thImg" src="/thumb/'+name+'?v='+Date.now()+'" style="width:100%;border-radius:12px;border:1px solid var(--line);margin-top:14px">'+
    '<div class="done"><a class="dl" id="thDl" href="/thumb/'+name+'?dl=1">⬇ Download thumbnail</a></div>'
    : '<div id="thImgWrap"></div>';
  return '<div class="card" style="margin-top:24px"><h1 style="font-size:20px">Thumbnail</h1>'+
    '<p class="sub" style="margin-bottom:0">A bold 1280×720 thumbnail from one of your doodle frames — free, no image credits.</p>'+
    '<label>Title text</label><input type="text" id="thTitle" value="'+esc(p.title)+'">'+
    '<label>Doodle frame <span style="color:var(--mut);font-weight:400">(0–'+(Math.max(0,n-1))+')</span></label>'+
    '<input type="number" id="thFrame" value="0" min="0" max="'+(Math.max(0,n-1))+'" style="width:120px">'+
    '<div class="row" style="margin-top:18px"><button type="button" id="thBtn" class="primary" style="margin-top:0">🖼 Generate thumbnail</button></div>'+
    '<div id="thStatus" class="detail" style="margin-top:10px"></div>'+preview+'</div>';
}
function wireThumb(name,p){
  const btn=document.getElementById('thBtn'); if(!btn) return;
  const st=document.getElementById('thStatus');
  btn.onclick=async()=>{
    btn.disabled=true; const o=btn.textContent; btn.textContent='Composing…'; st.textContent='';
    let j; try{ j=await (await fetch('/thumbnail/'+name,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:document.getElementById('thTitle').value,
        image_index:parseInt(document.getElementById('thFrame').value)||0})})).json(); }
    catch(e){ j={error:''+e}; }
    btn.disabled=false; btn.textContent=o;
    if(j.error){st.innerHTML='<span class="err">'+esc(j.error)+'</span>'; return;}
    st.textContent='Made from frame '+j.frame+' of '+j.frames+'.';
    let img=document.getElementById('thImg');
    if(!img){const w=document.getElementById('thImgWrap');
      w.innerHTML='<img id="thImg" style="width:100%;border-radius:12px;border:1px solid var(--line);margin-top:14px">'+
        '<div class="done"><a class="dl" id="thDl" href="/thumb/'+name+'?dl=1">⬇ Download thumbnail</a></div>';
      img=document.getElementById('thImg');}
    img.src=j.url;
  };
}
function ta(id,val,h){return '<textarea id="'+id+'" style="height:'+h+'px">'+esc(val)+'</textarea>';}
function publishCard(name,p){
  let pub = p.yt_url ? '<div class="done" style="margin-bottom:14px">▶ Published: '+
      '<a class="dl" style="background:#26262f;color:var(--txt)" href="'+esc(p.yt_url)+
      '" target="_blank">'+esc(p.yt_url)+'</a></div>' : '';
  let setup = p.yt_ready ? '' :
    '<div class="titles">First time: add <code>client_secret.json</code> to the repo '+
    'root — see <code>docs/youtube-setup.md</code>. The first publish opens a browser '+
    'to authorize.</div>';
  return '<div class="card" style="margin-top:24px"><h1 style="font-size:20px">Publish to YouTube</h1>'+
    pub+setup+
    '<label>Title</label><input type="text" id="ytTitle" value="'+esc(p.yt_title)+'">'+
    '<label>Description</label>'+ta('ytDesc',p.yt_description,160)+
    '<label>Tags <span style="color:var(--mut);font-weight:400">(comma separated)</span></label>'+
    '<input type="text" id="ytTags" value="'+esc(p.yt_tags)+'">'+
    '<label>Privacy</label>'+
    '<select id="ytPriv" style="width:100%;padding:11px 12px;background:#0f0f14;border:1px solid var(--line);border-radius:10px;color:var(--txt);font:inherit">'+
      ['unlisted','private','public'].map(o=>'<option value="'+o+'"'+
        (o===(p.privacy||'unlisted')?' selected':'')+'>'+o+'</option>').join('')+'</select>'+
    '<div class="row" style="margin-top:18px">'+
      '<button type="button" id="ytGen" style="background:#26262f;border:1px solid var(--line)">✨ Generate with Claude</button>'+
      '<button type="button" id="ytPub" class="primary" style="margin-top:0;flex:1">🚀 Publish to YouTube</button>'+
    '</div>'+
    '<div id="ytStatus" style="display:none;margin-top:14px"><div class="stat">'+
      '<div class="spin" id="ytSpin"></div><div><div class="stage" id="ytStage"></div>'+
      '<div class="detail" id="ytDetail"></div></div></div></div>';
}
function wirePublish(name,p){
  const gen=document.getElementById('ytGen'), pub=document.getElementById('ytPub'),
        st=document.getElementById('ytStatus'), stage=document.getElementById('ytStage'),
        det=document.getElementById('ytDetail'), spin=document.getElementById('ytSpin');
  if(!pub) return;
  const fields=()=>({title:document.getElementById('ytTitle').value,
    description:document.getElementById('ytDesc').value,
    tags:document.getElementById('ytTags').value,
    privacy:document.getElementById('ytPriv').value});
  gen.onclick=async()=>{
    gen.disabled=true; const o=gen.textContent; gen.textContent='Generating… (~30s)';
    try{
      const r=await fetch('/metadata',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({topic:p.yt_title||p.title, script:p.script||''})});
      const j=await r.json();
      if(!j.error){
        if(j.title)document.getElementById('ytTitle').value=j.title;
        if(j.description)document.getElementById('ytDesc').value=j.description;
        if(j.tags)document.getElementById('ytTags').value=j.tags;
        fetch('/save_meta/'+name,{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify(fields())});
      }
    }catch(e){}
    gen.disabled=false; gen.textContent=o;
  };
  pub.onclick=async()=>{
    pub.disabled=true; gen.disabled=true; st.style.display='block'; spin.style.display='block';
    stage.textContent='Starting…'; det.textContent='';
    await fetch('/save_meta/'+name,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(fields())});
    let j; try{ j=await (await fetch('/publish/'+name,{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(fields())})).json(); }
    catch(e){ j={error:''+e}; }
    if(j.error){stage.textContent='Error'; spin.style.display='none';
      det.innerHTML='<span class="err">'+esc(j.error)+'</span>'; pub.disabled=false; gen.disabled=false; return;}
    const names={auth:'Authorizing with YouTube',uploading:'Uploading to YouTube'};
    const t=setInterval(async()=>{
      const s=await (await fetch('/status/'+j.job)).json();
      stage.textContent=names[s.stage]||s.stage; det.textContent=s.detail||'';
      if(s.stage==='auth'){det.textContent='A browser window may open for you to approve access.';}
      if(s.done){
        clearInterval(t); spin.style.display='none'; pub.disabled=false; gen.disabled=false;
        if(s.error){stage.textContent='Error'; det.innerHTML='<span class="err">'+esc(s.error)+'</span>';}
        else{stage.textContent='Published ✅';
          det.innerHTML='<a class="dl" href="'+esc(s.url)+'" target="_blank">▶ '+esc(s.url)+'</a>';}
      }
    },1500);
  };
}
async function openProject(name){
  builderView.style.display='none'; detailView.style.display='block';
  detailView.innerHTML='<p class="sub">Loading…</p>'; loadProjects(name);
  let p; try{p=await (await fetch('/project/'+name)).json();}
  catch(e){detailView.innerHTML='<p class="err">Failed to load.</p>'; return;}
  if(p.error){detailView.innerHTML='<p class="err">'+esc(p.error)+'</p>'; return;}
  let h='<h1>'+esc(p.title)+'</h1>';
  if(p.has_video){h+='<video controls src="/video/'+name+'?v='+Date.now()+'"></video>'+
    '<div class="done"><a class="dl" href="/video/'+name+'?dl=1">⬇ Download MP4</a>'+
    (p.video_path?'<div class="path">'+esc(p.video_path)+'</div>':'')+'</div>';}
  else{h+='<p class="sub">No video rendered yet for this project.</p>';}
  if(p.has_vo){h+='<label>Voiceover</label><audio controls src="/audio/'+name+'"></audio>';}
  h+='<div class="path" style="margin-top:14px">'+(p.image_count||0)+' images generated</div>';
  if(p.script){h+=field('Script',p.script,180);}
  if(p.transcript){h+=field('Transcript (timed)',p.transcript,160);}
  if(p.image_count){h+=thumbCard(name,p);}
  if(p.has_video){h+=publishCard(name,p);}
  detailView.innerHTML=h;
  if(p.image_count){wireThumb(name,p);}
  if(p.has_video){wirePublish(name,p);}
}
loadProjects();
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/build", methods=["POST"])
def build():
    name = _slug(request.form.get("name", ""))
    proj = PROJECTS / name
    proj.mkdir(parents=True, exist_ok=True)
    audio = request.files.get("audio")
    if audio and audio.filename:                     # an uploaded file wins
        ext = pathlib.Path(audio.filename).suffix.lower() or ".mp3"
        vo = proj / f"vo{ext}"
        audio.save(str(vo))
    else:                                            # else use a VO already in the folder
        vo = _find_vo(proj)
        if not vo:
            return jsonify(error="No voiceover — upload one or click "
                                 "“Generate voiceover” first."), 400
    script = (request.form.get("script") or "").strip()
    if script:
        (proj / "script.txt").write_text(script, encoding="utf-8")
    try:
        spi = float(request.form.get("seconds_per_image") or 0) or None
    except ValueError:
        spi = None

    job = uuid.uuid4().hex[:8]
    JOBS[job] = {"stage": "queued", "detail": "", "done": False, "error": None, "project": name}

    def run():
        def pr(stage, detail=""):
            JOBS[job]["stage"] = stage
            JOBS[job]["detail"] = detail
        try:
            build_project(str(proj), audio_path=str(vo), progress=pr, seconds_per_image=spi)
            JOBS[job].update(stage="done", done=True,
                             video_path=str((proj / "video.mp4").resolve()))
        except NeedImages:
            JOBS[job].update(done=True, error="No OPENAI_API_KEY set — can't generate images.")
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            JOBS[job].update(done=True, error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job=job)


@app.route("/voiceover", methods=["POST"])
def make_voiceover():
    """Synthesize a VO from the script via ElevenLabs, save it into the project."""
    data = request.get_json(silent=True) or {}
    name = _slug(data.get("name", ""))
    script = (data.get("script") or "").strip()
    voice_id = (data.get("voice_id") or "").strip() or None
    if not script:
        return jsonify(error="Write or paste a script first."), 400
    if not voiceover.available():
        return jsonify(error="No ELEVENLABS_API_KEY set in .env — "
                             "add it (and ELEVENLABS_VOICE_ID), or upload your own VO."), 400
    proj = PROJECTS / name
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "script.txt").write_text(script, encoding="utf-8")

    job = uuid.uuid4().hex[:8]
    JOBS[job] = {"stage": "voiceover", "detail": "", "done": False, "error": None, "project": name}

    def run():
        def pr(i, n):
            JOBS[job]["detail"] = f"Narrating chunk {i}/{n}"
        try:
            vo = proj / "vo.mp3"
            voiceover.synthesize(script, str(vo), voice_id=voice_id, on_progress=pr)
            JOBS[job].update(stage="done", done=True, audio=True,
                             video_path=str(vo.resolve()))
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            JOBS[job].update(done=True, error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job=job, chars=voiceover.estimate_chars(script))


@app.route("/script", methods=["POST"])
def script():
    topic = (request.get_json(silent=True) or {}).get("topic", "").strip()
    if not topic:
        return jsonify(error="Please enter a topic."), 400
    try:
        # Uses the Claude Code CLI on your subscription — no API credits.
        result = script_writer.generate_via_claude_code(topic)
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)), 500


@app.route("/metadata", methods=["POST"])
def metadata():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    script = (data.get("script") or "").strip()
    if not topic:
        return jsonify(error="Enter a topic (or project name) first."), 400
    try:
        return jsonify(script_writer.generate_metadata_via_claude_code(topic, script))
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)), 500


@app.route("/save_meta/<name>", methods=["POST"])
def save_meta(name):
    d = PROJECTS / _slug(name)
    if not d.is_dir():
        return jsonify(error="Project not found"), 404
    data = request.get_json(silent=True) or {}
    meta = _read_meta(d)
    for k in ("title", "description", "tags", "privacy"):
        if k in data:
            meta[k] = (data.get(k) or "").strip() if isinstance(data.get(k), str) else data.get(k)
    _write_meta(d, meta)
    return jsonify(ok=True)


@app.route("/publish/<name>", methods=["POST"])
def publish(name):
    d = PROJECTS / _slug(name)
    if not d.is_dir():
        return jsonify(error="Project not found"), 404
    video = d / "video.mp4"
    if not video.exists():
        return jsonify(error="No rendered video to publish yet."), 400
    if not youtube_upload.configured():
        return jsonify(error="YouTube isn’t set up yet — add client_secret.json "
                             "(see docs/youtube-setup.md), then try again."), 400

    data = request.get_json(silent=True) or {}
    meta = _read_meta(d)
    title = (data.get("title") or meta.get("title") or d.name).strip()
    description = (data.get("description") or meta.get("description") or "").strip()
    tags = data.get("tags", meta.get("tags", ""))
    privacy = (data.get("privacy") or meta.get("privacy") or "unlisted").strip()
    meta.update(title=title, description=description, tags=tags, privacy=privacy)
    _write_meta(d, meta)

    job = uuid.uuid4().hex[:8]
    JOBS[job] = {"stage": "auth", "detail": "Checking YouTube authorization…",
                 "done": False, "error": None, "project": d.name}

    def run():
        def pr(pct):
            JOBS[job].update(stage="uploading", detail=f"Uploading… {pct}%")
        try:
            res = youtube_upload.upload(str(video), title=title, description=description,
                                        tags=tags, privacy=privacy, on_progress=pr)
            m = _read_meta(d)
            m.update(youtube_id=res["id"], youtube_url=res["url"], privacy=privacy)
            _write_meta(d, m)
            JOBS[job].update(stage="done", done=True, url=res["url"], video_id=res["id"])
        except youtube_upload.NeedsAuthSetup as e:
            JOBS[job].update(done=True, error=str(e))
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            JOBS[job].update(done=True, error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job=job)


@app.route("/config")
def config():
    return jsonify(seconds_per_image=float(os.getenv("SECONDS_PER_IMAGE", "4")),
                   quality=os.getenv("IMAGE_QUALITY", "low"),
                   tts_available=voiceover.available())


@app.route("/status/<job>")
def status(job):
    return jsonify(JOBS.get(job, {"error": "unknown job", "done": True}))


_AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".aiff", ".ogg")


def _find_vo(d: pathlib.Path):
    for p in sorted(d.glob("vo.*")) + sorted(d.glob("*")):
        if p.is_file() and p.suffix.lower() in _AUDIO_EXT:
            return p
    return None


@app.route("/projects")
def projects():
    out = []
    if PROJECTS.exists():
        dirs = [d for d in PROJECTS.iterdir() if d.is_dir()]
        for d in sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True):
            out.append({"name": d.name,
                        "title": d.name.replace("-", " ").replace("_", " ").title(),
                        "has_video": (d / "video.mp4").exists()})
    return jsonify(out)


@app.route("/project/<name>")
def project(name):
    d = PROJECTS / _slug(name)
    if not d.is_dir():
        return jsonify(error="Project not found"), 404

    def read(f):
        p = d / f
        return p.read_text(encoding="utf-8") if p.exists() else ""

    imgs = d / "images"
    has_video = (d / "video.mp4").exists()
    meta = _read_meta(d)
    pretty = d.name.replace("-", " ").replace("_", " ").title()
    return jsonify(
        name=d.name, title=pretty,
        has_video=has_video,
        video_path=str((d / "video.mp4").resolve()) if has_video else "",
        has_vo=bool(_find_vo(d)),
        script=read("script.txt"), transcript=read("transcript.txt"),
        image_count=len(list(imgs.glob("*.png"))) if imgs.exists() else 0,
        has_thumb=(d / "thumbnail.png").exists(),
        # YouTube publish state
        yt_title=meta.get("title") or pretty,
        yt_description=meta.get("description", ""),
        yt_tags=meta.get("tags", ""),
        yt_video_id=meta.get("youtube_id", ""),
        yt_url=meta.get("youtube_url", ""),
        yt_ready=youtube_upload.configured(),
    )


def _doodle_frames(d: pathlib.Path):
    imgs = d / "images"
    return sorted(imgs.glob("*.png")) if imgs.exists() else []


@app.route("/thumbnail/<name>", methods=["POST"])
def make_thumb(name):
    d = PROJECTS / _slug(name)
    if not d.is_dir():
        return jsonify(error="Project not found"), 404
    frames = _doodle_frames(d)
    if not frames:
        return jsonify(error="No doodle images yet — render the video first."), 400
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or d.name.replace("-", " ")).strip()
    try:
        idx = int(data.get("image_index", 0))
    except (TypeError, ValueError):
        idx = 0
    idx = max(0, min(idx, len(frames) - 1))
    try:
        thumbnail.make_thumbnail(str(frames[idx]), title, str(d / "thumbnail.png"))
    except Exception as e:  # noqa: BLE001 - surface to UI
        return jsonify(error=str(e)), 500
    return jsonify(ok=True, frame=idx, frames=len(frames),
                   url=f"/thumb/{d.name}?v={uuid.uuid4().hex[:6]}")


@app.route("/thumb/<name>")
def thumb(name):
    p = PROJECTS / _slug(name) / "thumbnail.png"
    if not p.exists():
        abort(404)
    return send_file(str(p), as_attachment=bool(request.args.get("dl")),
                     download_name=f"{_slug(name)}-thumb.png")


@app.route("/audio/<name>")
def audio(name):
    vo = _find_vo(PROJECTS / _slug(name))
    if not vo:
        abort(404)
    return send_file(str(vo))


@app.route("/video/<name>")
def video(name):
    p = PROJECTS / _slug(name) / "video.mp4"
    if not p.exists():
        abort(404)
    return send_file(str(p), as_attachment=bool(request.args.get("dl")),
                     download_name=f"{_slug(name)}.mp4")


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", "8000"))  # 8000 default: avoids macOS AirPlay on 5000
    print(f"Doodle Studio → http://localhost:{port}")
    app.run(host="127.0.0.1", port=port)
