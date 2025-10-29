# Deploy Brushograph Optimizer to Render

This guide deploys the FastAPI wrapper for `scripts/complete_gcode_optimizer.py` as a Web Service on Render.

## Repo structure
```
<repo-root>/
├─ scripts/
│  └─ complete_gcode_optimizer.py
└─ webapi/
   ├─ main.py
   ├─ requirements.txt
   └─ render.yaml   # optional, helps pre-fill settings on Render
```

## Local test
```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r webapi/requirements.txt
uvicorn webapi.main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

## Deploy on Render (Dashboard)
1) Push this repo to GitHub.
2) In Render, click New → Web Service → Connect your repo.
3) Settings:
   - Region: EU (Frankfurt) or your preference
   - Build Command: `pip install -r webapi/requirements.txt`
   - Start Command: `uvicorn webapi.main:app --host 0.0.0.0 --port $PORT`
   - Environment: Python 3.10+
   - Plan: Free is OK
4) Create Web Service and wait for the build.
5) Open the public URL.

## API
- GET `/` → HTML form to upload `.gcode`
- POST `/optimize` (multipart/form-data):
  - `file`: `.gcode` file
  - `distance` (float, default 100)
  - `force_multiplier` (float, default 2.0)
  - `aggressive` (bool)
  - `debug` (bool)
- GET `/healthz` → `{ "status": "ok" }`

## Notes
- The server imports your optimizer from `scripts/complete_gcode_optimizer.py`.
- Uploads are written to a temporary directory and cleaned up after response.
- CORS is enabled for all origins by default.
- For heavy traffic, consider adding simple rate-limiting or auth.
