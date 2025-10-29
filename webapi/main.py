import os
import sys
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure we can import the optimizer from scripts/
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from complete_gcode_optimizer import optimize_gcode
except Exception as e:
    # Provide a helpful error when import fails on the deployed service
    def optimize_gcode(*args, **kwargs):  # type: ignore
        raise RuntimeError("Failed to import optimizer. Ensure scripts/complete_gcode_optimizer.py exists.")

app = FastAPI(title="Brushograph G-code Optimizer API")

# Allow cross-origin for simple browser clients (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX_HTML = """
<!doctype html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Brushograph G-code Optimizer</title>
    <style>
      /* Theme tokens */
      :root {
        /* Light theme */
        --bg1: #f8fafc; /* slate-50 */
        --bg2: #eef2ff; /* indigo-50 */
        --card: #ffffff;
        --text: #0f172a; /* slate-900 */
        --muted: #475569; /* slate-600 */
        --outline: #e2e8f0; /* slate-200 */
        --accent: #ec4899; /* pink-500 */
        --accent-2: #22d3ee; /* cyan-400 */
        --glow-a: rgba(236,72,153,0.22);
        --glow-b: rgba(34,211,238,0.22);
        --ok: #16a34a; /* green-600 */
      }
      html[data-theme='dark'] {
        /* Cyberpunk dark */
        --bg1: #0b0f19;
        --bg2: #0c1222;
        --card: #0a0f1a;
        --text: #e5e7eb;
        --muted: #94a3b8;
        --outline: #1f2a44;
        --accent: #ff2dac; /* neon pink */
        --accent-2: #29e0ff; /* neon cyan */
        --glow-a: rgba(255,45,172,0.22);
        --glow-b: rgba(41,224,255,0.22);
        --ok: #34d399;
      }
      * { box-sizing: border-box; }
      html, body { height: 100%; }
      body {
        margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Apple Color Emoji", "Segoe UI Emoji";
        color: var(--text);
        background: radial-gradient(1200px 800px at 5% -10%, var(--glow-b), transparent 60%),
                    radial-gradient(1200px 800px at 110% 10%, var(--glow-a), transparent 60%),
                    linear-gradient(180deg, var(--bg1), var(--bg2));
        display: grid; place-items: center; padding: 2rem;
      }
      .card { width: 100%; max-width: 960px; background: var(--card); border: 1px solid var(--outline); border-radius: 16px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
      .header { padding: 1.1rem 1.25rem; border-bottom: 1px solid var(--outline); display: flex; align-items: center; gap: .9rem; justify-content: space-between; }
      .brand { display:flex; align-items:center; gap:.9rem; }
      .logo { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #0b1220; font-weight: 900; box-shadow: 0 0 18px var(--glow-a), 0 0 18px var(--glow-b); }
      h1 { margin: 0; font-size: 1.2rem; letter-spacing: .2px; }
      .sub { color: var(--muted); margin-top: .15rem; font-size: .95rem; }
      .theme-toggle { border: 1px solid var(--outline); background: transparent; color: var(--text); padding: .55rem .7rem; border-radius: 10px; cursor: pointer; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1.1rem; }
      @media (max-width: 820px) { .grid { grid-template-columns: 1fr; } }
      fieldset { border: 1px solid var(--outline); border-radius: 12px; padding: 1rem; background: color-mix(in oklab, var(--card), black 4%); }
      legend { padding: 0 .4rem; color: var(--muted); }
      label { display:block; margin-top: .8rem; font-size: .95rem; }
      input[type="number"], input[type="text"], input[type="file"] { width: 100%; margin-top: .35rem; padding: .7rem .8rem; border-radius: 10px; border: 1px solid var(--outline); background: color-mix(in oklab, var(--card), black 6%); color: var(--text); }
      input[type="checkbox"] { transform: scale(1.15); margin-right: .5rem; }
      .row { display: flex; align-items: center; gap: .5rem; margin-top: .6rem; }
      .submit { display: inline-flex; align-items: center; gap: .5rem; margin: 1.1rem 1.25rem 1.25rem; padding: .85rem 1.2rem; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #0b1220; font-weight: 800; letter-spacing: .2px; border: none; border-radius: 12px; cursor: pointer; box-shadow: 0 0 24px var(--glow-a), 0 0 24px var(--glow-b); }
      .submit:hover { filter: brightness(1.05); }
      .footer { border-top: 1px solid var(--outline); padding: .85rem 1.25rem; color: var(--muted); font-size: .9rem; display:flex; justify-content: space-between; align-items:center; }
      .badge { background: color-mix(in oklab, var(--accent-2), transparent 80%); color: var(--text); padding: .25rem .5rem; border-radius: 999px; font-size:.8rem; border:1px solid var(--outline) }
    </style>
  </head>
  <body>
    <div class="card">
      <div class="header">
        <div class="brand">
          <div class="logo">B</div>
          <div>
            <h1>Brushograph G-code Optimizer</h1>
            <div class="sub">Upload .gcode → neon‑cleaned output with color sequences and safe moves.</div>
          </div>
        </div>
        <button id="toggleTheme" class="theme-toggle" type="button" title="Toggle light/dark"> Toggle theme</button>
      </div>
      <form id="form" method="post" action="/optimize" enctype="multipart/form-data">
        <div class="grid">
          <fieldset>
            <legend>Upload</legend>
            <label>G-code file (.gcode)
              <input type="file" name="file" accept=".gcode" required />
            </label>
          </fieldset>
          <fieldset>
            <legend>Options</legend>
            <label>Distance threshold (mm)
              <input type="number" step="0.1" name="distance" value="100" />
            </label>
            <label>Force multiplier
              <input type="number" step="0.1" name="force_multiplier" value="2.0" />
            </label>
            <label class="row"><input type="checkbox" name="aggressive" /> Aggressive mode</label>
            <label class="row"><input type="checkbox" name="debug" /> Debug output (server logs)</label>
            <label class="row"><input type="checkbox" id="showlog" /> Show log on page</label>
          </fieldset>
        </div>
        <div style="display:flex; gap:.75rem; align-items:center; padding: 0 1.25rem 1.25rem;">
          <button class="submit" type="submit" title="Optimize and download"> Optimize G-code</button>
          <button class="submit" type="submit" formaction="/optimize_preview" title="Show log and download"> Preview with log</button>
        </div>
      </form>
      <div class="footer">
        <span>Files processed ephemerally, not stored.</span>
        <span class="badge">online</span>
      </div>
    </div>
    <script>
      (function(){
        const root = document.documentElement;
        const key = 'bg-theme';
        const apply = (theme) => root.setAttribute('data-theme', theme);
        const saved = localStorage.getItem(key);
        if (saved === 'light' || saved === 'dark') apply(saved);
        const btn = document.getElementById('toggleTheme');
        btn?.addEventListener('click', () => {
          const next = (root.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
          apply(next);
          localStorage.setItem(key, next);
        });
        // Route form to preview endpoint if Show log is checked
        const form = document.getElementById('form');
        form?.addEventListener('submit', (e) => {
          const showlog = document.getElementById('showlog');
          if (showlog && showlog.checked) {
            form.action = '/optimize_preview';
          } else {
            form.action = '/optimize';
          }
        });
      })();
    </script>
  </body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

@app.post("/optimize")
async def optimize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    distance: float = Form(100.0),
    force_multiplier: float = Form(2.0),
    aggressive: Optional[bool] = Form(False),
    debug: Optional[bool] = Form(False),
):
    # Validate filename
    original_name = file.filename or f"upload_{uuid.uuid4().hex}.gcode"
    if not original_name.lower().endswith(".gcode"):
        return PlainTextResponse("Please upload a .gcode file.", status_code=400)

    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_opt_"))
    in_path = tmp_dir / original_name
    out_name = original_name.rsplit(".gcode", 1)[0] + "_optimized.gcode"
    out_path = tmp_dir / out_name

    try:
        # Save upload
        with in_path.open("wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        # Run optimization
        # optimize_gcode signature: (input_file, output_file=None, distance_threshold=100, force_multiplier=2.0, debug=False, aggressive=False)
        optimize_gcode(
            str(in_path),
            str(out_path),
            float(distance),
            float(force_multiplier),
            bool(debug),
            bool(aggressive),
        )

        # Schedule cleanup of temp directory after response is sent
        def _cleanup(path: Path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

        background_tasks.add_task(_cleanup, tmp_dir)

        return FileResponse(
            path=str(out_path),
            filename=out_name,
            media_type="text/plain",
        )
    except Exception as e:
        # In case of error, cleanup and return message
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        return PlainTextResponse(f"Optimization failed: {e}", status_code=500)

# Preview endpoint: returns HTML with log output and a data-URL download link
@app.post("/optimize_preview")
async def optimize_preview(
    file: UploadFile = File(...),
    distance: float = Form(100.0),
    force_multiplier: float = Form(2.0),
    aggressive: Optional[bool] = Form(False),
    debug: Optional[bool] = Form(False),
):
    import io, base64, contextlib
    original_name = file.filename or f"upload_{uuid.uuid4().hex}.gcode"
    if not original_name.lower().endswith(".gcode"):
        return PlainTextResponse("Please upload a .gcode file.", status_code=400)

    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_opt_"))
    in_path = tmp_dir / original_name
    out_name = original_name.rsplit(".gcode", 1)[0] + "_optimized.gcode"
    out_path = tmp_dir / out_name

    try:
        with in_path.open("wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            optimize_gcode(
                str(in_path),
                str(out_path),
                float(distance),
                float(force_multiplier),
                bool(debug),
                bool(aggressive),
            )
        log_text = buf.getvalue()

        # Read optimized content and embed as base64 data URL
        optimized_text = out_path.read_text(encoding="utf-8", errors="ignore")
        b64 = base64.b64encode(optimized_text.encode("utf-8")).decode("ascii")
        data_url = f"data:text/plain;base64,{b64}"

        # Cleanup temp dir now that content is embedded
        shutil.rmtree(tmp_dir, ignore_errors=True)

        html = f"""
<!doctype html>
<html lang=\"en\" data-theme=\"dark\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Optimization Result</title>
    <style>
      body {{ margin:0; font-family: ui-sans-serif, system-ui; background:#0b0f19; color:#e5e7eb; padding:1rem; }}
      .wrap {{ max-width: 1000px; margin: 0 auto; }}
      .top {{ display:flex; justify-content: space-between; align-items: center; gap: .8rem; }}
      a.btn {{ display:inline-block; padding:.6rem .9rem; border-radius:10px; background: linear-gradient(135deg,#ff2dac,#29e0ff); color:#0b1220; font-weight:800; text-decoration:none; box-shadow: 0 0 20px rgba(255,45,172,.25), 0 0 20px rgba(41,224,255,.25); }}
      pre {{ white-space: pre-wrap; background:#0a0f1a; border:1px solid #1f2a44; padding:1rem; border-radius:12px; overflow:auto; }}
      .meta {{ color:#94a3b8; margin:.6rem 0 1rem; }}
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"top\">
        <h2 style=\"margin:.2rem 0;\">Optimization complete</h2>
        <a class=\"btn\" href=\"{data_url}\" download=\"{out_name}\">Download optimized G-code</a>
      </div>
      <div class=\"meta\">Source: {original_name} • Distance: {distance} • Force: {force_multiplier} • Aggressive: {bool(aggressive)}</div>
      <pre>{log_text}</pre>
      <p class=\"meta\"><a href=\"/\" style=\"color:#29e0ff\">← Back</a></p>
    </div>
  </body>
</html>
"""
        return HTMLResponse(html)
    except Exception as e:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        return PlainTextResponse(f"Optimization failed: {e}", status_code=500)

# Health check for Render
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
