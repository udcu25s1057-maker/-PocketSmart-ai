# PocketSmart AI

A budget-planning web app for home setup, events, and jewelry. It uses FastAPI, SQLite, and optional Google Gemini recommendations. Without a Gemini API key, the app uses its built-in budget-aware fallback planner.

## Run on Windows PowerShell

Create and activate the virtual environment:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install dependencies and start the server:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API documentation is at http://127.0.0.1:8000/docs.

If script activation is restricted by your organization, use `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` without activating.

## Configuration

Copy `.env.example` to `.env`. Set a long random `SECRET_KEY` before deployment. `GEMINI_API_KEY` is optional; without it, planning uses local fallback recommendations. `GEMINI_MODEL`, `DATABASE_PATH`, and `MAX_UPLOAD_MB` can also be configured.

The SQLite database is created under `data/` by default. Uploaded outfit images are validated and processed in memory; they are not stored.
