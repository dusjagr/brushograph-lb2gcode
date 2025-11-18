# Brushograph G-code Optimizer

Beginner-friendly web page to upload a .gcode file and download an optimized version. You can also run the optimizer from the command line if you prefer.

## Requirements
- Python 3.8+ (recommended 3.10+)
- This repository (cloned locally)

## Option A — Use the Web UI (easiest)
1) Start the local server from the repo root:
```bash
uvicorn webapi.main:app --host 0.0.0.0 --port 8001
```
2) Open your browser at:
```
http://localhost:8001
```
3) Upload your .gcode file and choose options:
- Distance threshold (mm): how far you can draw before picking up more paint.
- Force multiplier: hard limit, e.g. 2.0 × threshold.
- Aggressive mode: insert pickups as soon as threshold is exceeded.
- Debug output: print extra details in logs.
- Show log on page: see the optimizer output right in the browser.

4) Click one of the buttons:
- Optimize G-code: downloads the optimized file directly.
- Preview with log: shows a results page with the full log and a download button.

Extras:
- Cyberpunk neon theme with dark/light toggle (persists in your browser).
- Health endpoint: GET /healthz returns {"status":"ok"}.

## Option B — Command-line (single-file usage)
This is the same optimizer, run directly without the web UI.

Quick start:
```bash
# From the repository root or the scripts folder
python3 scripts/complete_gcode_optimizer.py <input.gcode>
# Output defaults to <input>_optimized.gcode
```

Common usage:
- Specify output file:
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -o output.gcode
```
- Change pickup distance threshold (mm):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -d 120
```
- Only force pickups beyond a multiple of the threshold (default 2.0):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode -d 100 -f 2.5
```
- Enable debug logs:
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --debug
```
- Aggressive mode (insert pickups anywhere after threshold):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --aggressive
```
- Analyze structure only (no changes written):
```bash
python3 scripts/complete_gcode_optimizer.py input.gcode --analyze
```

## What it does
- Adds homing header and a clean ending sequence.
- Formats G-code for the miniPenzlograf painting CNC:
  - Uses `G0` for positioning and `G1` for drawing.
  - Manages Z moves as separate, safe operations.
  - Simplifies some Z values and maintains clean feedrate usage.
- Inserts color pick-up sequences at layer starts and when path length exceeds the threshold.
- Inserts washing sequences when changing colors.
- Picks clean transition points (Z-lifts, end-of-stroke) and only returns to the previous XY if a stroke was interrupted.

## Notes
- No external dependencies; it uses only Python standard library.
- You can mark layers in your input with comments like `;Layer Green`, `;Layer Blue`, etc. The script maps these to built‑in color and washing sequences.
- Default preferences match the miniPenzlograf setup. If you need different color locations or sequences, edit the block constants near the top of the script.

## Examples
```bash
# Basic run
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode

# Custom output name + debug
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode -o MAG_new_fixed.gcode --debug

# Larger threshold, force later
python3 scripts/complete_gcode_optimizer.py MAG_new.gcode -d 150 -f 2.5
```

## Make it executable (optional)
```bash
chmod +x scripts/complete_gcode_optimizer.py
./scripts/complete_gcode_optimizer.py input.gcode
```

## Deploy to Render (host it online)
This repo includes `webapi/render.yaml` for one-click deploys on Render.
- Connect your GitHub repo on Render and create a Web Service.
- Render auto-builds and deploys on each push.
- Default start command: `uvicorn webapi.main:app --host 0.0.0.0 --port 10000` (handled by Render).

## Troubleshooting
- Port already in use: pick another port, e.g. `--port 8002`.
- Logs don’t show on the page: use “Preview with log” or tick “Show log on page”.
- Import error in web UI: make sure `scripts/complete_gcode_optimizer.py` exists in the repo path.
- Large files: give it time; keep the browser tab open until the file downloads or the preview appears.
