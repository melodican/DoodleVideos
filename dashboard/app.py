"""Local dashboard: upload a voiceover (+ optional script) -> synced doodle MP4.

Run:  python -m dashboard.app   then open http://localhost:5000
Needs OPENAI_API_KEY in the environment (transcription + images).
"""
from __future__ import annotations
import threading, uuid, re, pathlib
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
<!doctype html><html><head><meta charset="utf-8"><title>Doodle Studio</title>
<style>
 body{font:16px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1a1a1a}
 h1{font-size:24px} label{display:block;font-weight:600;margin:18px 0 6px}
 input[type=text],textarea{width:100%;padding:10px;border:1px solid #ccc;border-radius:8px;font:inherit;box-sizing:border-box}
 textarea{height:120px} input[type=file]{margin-top:6px}
 button{margin-top:22px;background:#111;color:#fff;border:0;border-radius:10px;padding:12px 22px;font:inherit;font-weight:600;cursor:pointer}
 button:disabled{opacity:.5;cursor:default}
 #status{margin-top:22px;padding:14px;border-radius:10px;background:#f4f4f5;display:none}
 .bar{height:8px;background:#e5e7eb;border-radius:6px;overflow:hidden;margin-top:8px}
 .bar>div{height:100%;width:0;background:#111;transition:width .3s}
 video{width:100%;margin-top:16px;border-radius:10px}
 a.dl{display:inline-block;margin-top:12px}
 small{color:#666}
</style></head><body>
<h1>🎬 Doodle Studio</h1>
<p><small>Upload your ElevenLabs voiceover. The script box is optional — timing comes from the audio.</small></p>
<form id="f">
  <label>Project name</label>
  <input type="text" name="name" placeholder="why-cities-never-sleep" required>
  <label>Voiceover (mp3 / m4a / wav)</label>
  <input type="file" name="audio" accept="audio/*" required>
  <label>Script <small>(optional — timing comes from the audio)</small></label>
  <div style="display:flex;gap:8px;align-items:center">
    <input type="text" id="topic" placeholder="Topic, e.g. What actually is tax?">
    <button type="button" id="gen" style="margin:0;white-space:nowrap">✨ Write with Claude</button>
  </div>
  <textarea name="script" id="script" placeholder="Paste a script, or generate one above. (Copy it into ElevenLabs to make your voiceover.)"></textarea>
  <div id="titles"><small></small></div>
  <button type="submit">Generate Video</button>
</form>
<div id="status"><b id="stage">Starting…</b><div class="bar"><div id="fill"></div></div>
  <div id="detail"><small></small></div><div id="result"></div></div>
<script>
const gen=document.getElementById('gen'), topic=document.getElementById('topic'),
      scriptBox=document.getElementById('script'), titles=document.querySelector('#titles small');
gen.onclick=async()=>{
  if(!topic.value.trim()){topic.focus();return;}
  gen.disabled=true; const old=gen.textContent; gen.textContent='Writing… (~30s)';
  titles.textContent='';
  try{
    const r=await fetch('/script',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({topic:topic.value.trim()})});
    const j=await r.json();
    if(j.error){titles.textContent='Error: '+j.error;}
    else{scriptBox.value=j.script; if(j.extras) titles.textContent=j.extras;}
  }catch(e){titles.textContent='Error: '+e;}
  gen.disabled=false; gen.textContent=old;
};
const f=document.getElementById('f'), s=document.getElementById('status'),
      stage=document.getElementById('stage'), fill=document.getElementById('fill'),
      detail=document.querySelector('#detail small'), result=document.getElementById('result'),
      btn=f.querySelector('button');
f.onsubmit=async e=>{
  e.preventDefault(); btn.disabled=true; s.style.display='block'; result.innerHTML='';
  stage.textContent='Uploading…'; fill.style.width='5%';
  const r=await fetch('/build',{method:'POST',body:new FormData(f)});
  const j=await r.json();
  if(j.error){stage.textContent='Error'; detail.textContent=j.error; btn.disabled=false; return;}
  poll(j.job);
};
function poll(job){
  const t=setInterval(async()=>{
    const j=await (await fetch('/status/'+job)).json();
    stage.textContent=({transcribe:'Transcribing',segments:'Planning',images:'Drawing',assemble:'Assembling',done:'Done ✅',queued:'Queued'}[j.stage]||j.stage);
    detail.textContent=j.detail||'';
    let m=(j.detail||'').match(/(\\d+)\\/(\\d+)/);
    if(j.stage==='images'&&m){fill.style.width=(10+80*m[1]/m[2])+'%';}
    else if(j.stage==='transcribe'){fill.style.width='8%';}
    else if(j.stage==='segments'){fill.style.width='10%';}
    else if(j.stage==='assemble'){fill.style.width='92%';}
    if(j.done){
      clearInterval(t); btn.disabled=false;
      if(j.error){stage.textContent='Error'; detail.textContent=j.error;}
      else{fill.style.width='100%';
        result.innerHTML='<video controls src="/video/'+j.project+'?v='+Date.now()+'"></video>'+
          '<a class="dl" href="/video/'+j.project+'?dl=1">⬇ Download MP4</a>';}
    }
  },1500);
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
            JOBS[job].update(stage="done", done=True)
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
