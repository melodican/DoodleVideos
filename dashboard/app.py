"""Local dashboard: upload a voiceover (+ optional script) -> synced doodle MP4.

Run:  python -m dashboard.app   then open http://localhost:5000
Needs OPENAI_API_KEY in the environment (transcription + images).
"""
from __future__ import annotations
import os, threading, uuid, re, pathlib
from flask import Flask, request, jsonify, render_template_string, send_file, abort

from pipeline.doodle.builder import build_project, NeedImages
from pipeline.doodle import script_writer

ROOT = pathlib.Path(__file__).parent.parent
PROJECTS = ROOT / "projects"
app = Flask(__name__)
JOBS: dict[str, dict] = {}


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "video"


PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Doodle Studio</title>
<style>
 :root{--bg:#0e0e12;--card:#17171d;--line:#2a2a33;--txt:#e9e9ee;--mut:#9a9aa6;
       --accent:#7c5cff;--accent2:#f5c542;--ok:#34d399}
 *{box-sizing:border-box}
 body{font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--txt);margin:0;padding:44px 16px}
 .wrap{max-width:680px;margin:0 auto}
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
</style></head><body><div class="wrap">
<h1>🎬 Doodle Studio</h1>
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
  <label>Voiceover (mp3 / m4a / wav)</label>
  <input type="file" name="audio" accept="audio/*" required>
  <div class="est" id="est"></div>
  <button type="submit" class="primary">Generate Video</button>
</form>
<div id="status">
  <div class="stat"><div class="spin" id="spin"></div>
    <div><div class="stage" id="stage">Starting…</div><div class="detail" id="detail"></div></div></div>
  <div class="bar"><div id="fill"></div></div>
  <div id="result"></div>
</div>
</div></div>
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
          (j.video_path?'<div class="path">Saved at: '+j.video_path+'</div>':'')+'</div>';}
    }
  },1500);
}
// --- live cost estimate (no API call; reads audio length in the browser) ---
let CFG={seconds_per_image:8,quality:'low'}, audioDur=0;
const PRICE={low:0.02,medium:0.06,high:0.19};
const est=document.getElementById('est'), audioInput=document.querySelector('input[name=audio]');
fetch('/config').then(r=>r.json()).then(c=>{CFG=c; recalc();}).catch(()=>{});
audioInput.onchange=()=>{
  const file=audioInput.files[0]; if(!file){audioDur=0; est.textContent=''; return;}
  const a=document.createElement('audio'); a.preload='metadata';
  a.onloadedmetadata=()=>{audioDur=a.duration||0; recalc(); URL.revokeObjectURL(a.src);};
  a.src=URL.createObjectURL(file);
};
function recalc(){
  if(!audioDur){est.textContent=''; return;}
  const n=Math.max(1,Math.ceil(audioDur/(CFG.seconds_per_image||8)));
  const cost=n*(PRICE[CFG.quality]||PRICE.low);
  const mins=(audioDur/60).toFixed(1);
  est.textContent='Estimate: ~'+n+' images for a '+mins+' min video ≈ $'+cost.toFixed(2)+
    ' at '+CFG.quality+' quality (+~$0.01 transcription)';
}
</script></body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/build", methods=["POST"])
def build():
    name = _slug(request.form.get("name", ""))
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify(error="Please choose a voiceover file."), 400
    proj = PROJECTS / name
    proj.mkdir(parents=True, exist_ok=True)
    ext = pathlib.Path(audio.filename).suffix.lower() or ".mp3"
    vo = proj / f"vo{ext}"
    audio.save(str(vo))
    script = (request.form.get("script") or "").strip()
    if script:
        (proj / "script.txt").write_text(script, encoding="utf-8")

    job = uuid.uuid4().hex[:8]
    JOBS[job] = {"stage": "queued", "detail": "", "done": False, "error": None, "project": name}

    def run():
        def pr(stage, detail=""):
            JOBS[job]["stage"] = stage
            JOBS[job]["detail"] = detail
        try:
            build_project(str(proj), audio_path=str(vo), progress=pr)
            JOBS[job].update(stage="done", done=True,
                             video_path=str((proj / "video.mp4").resolve()))
        except NeedImages:
            JOBS[job].update(done=True, error="No OPENAI_API_KEY set — can't generate images.")
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            JOBS[job].update(done=True, error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job=job)


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


@app.route("/config")
def config():
    return jsonify(seconds_per_image=float(os.getenv("SECONDS_PER_IMAGE", "8")),
                   quality=os.getenv("IMAGE_QUALITY", "low"))


@app.route("/status/<job>")
def status(job):
    return jsonify(JOBS.get(job, {"error": "unknown job", "done": True}))


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
