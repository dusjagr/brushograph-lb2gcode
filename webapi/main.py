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
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Brushograph G-code Optimizer</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 860px; }
      fieldset { border: 1px solid #ccc; padding: 1rem; border-radius: 8px; }
      legend { font-weight: 600; }
      label { display:block; margin-top: .75rem; }
      input[type="number"], input[type="text"], input[type="file"] { width: 100%; max-width: 420px; }
      button { margin-top: 1rem; padding: .6rem 1rem; font-weight: 600; }
      small { color: #555; }
    </style>
  </head>
  <body>
    <h1>Brushograph G-code Optimizer</h1>
    <p>Upload a .gcode file and download the optimized version. Defaults match the mini Brushograph preferences.</p>
    <form id="form" method="post" action="/optimize" enctype="multipart/form-data">
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
        <label>Aggressive mode
          <input type="checkbox" name="aggressive" />
        </label>
        <label>Debug output (printed in server logs)
          <input type="checkbox" name="debug" />
        </label>
      </fieldset>
      <button type="submit">Optimize</button>
      <p><small>Note: Your file is processed in-memory/temporary storage and returned immediately.</small></p>
    </form>
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

# Health check for Render
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
