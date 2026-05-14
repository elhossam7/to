# Profile Extraction Console

A local full-stack app for turning messy `.txt` people-profile files into structured JSON with FastAPI, Ollama, and a Vite React operations console.

## What It Does

- Watches `./data/inbox` for `.txt` files.
- Accepts single or multi-file `.txt` uploads from the React UI.
- Parses with minimal assumptions: trim lines and drop only empty lines.
- Sends raw lines to Ollama for context-aware profile extraction.
- Saves structured JSON profiles into `./data/profiles`.
- Appends audit events to `./data/audit.log`.
- Broadcasts pipeline events over SSE to the frontend.

## Run Locally

Backend:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Ollama

Start Ollama separately and make sure the configured model exists:

```powershell
ollama pull llama3.1
ollama serve
```

Change `OLLAMA_MODEL` in `.env` if you want another local model.

## Azure VM Deploy

Deployment assets live in `deploy/`:

- `profile-extraction.service` runs FastAPI on `127.0.0.1:8000`.
- `nginx-profile-extraction.conf` serves the React build on `127.0.0.1:8080` and proxies API/SSE traffic.
- `profile-extraction.env.example` configures `/data` storage and `qwen3-vl:235b-cloud`.
- `azure-vm.md` contains the full VM setup, update, tunnel, and smoke-test commands.

## API

- `POST /ingest` uploads and queues one `.txt` file.
- `POST /ingest-batch` uploads multiple `.txt` files and extracts one combined profile.
- `GET /profiles` lists saved profiles.
- `GET /profiles/{id}` loads one profile.
- `GET /events` streams pipeline updates.
- `GET /status` reports queue, worker, Ollama, and data paths.
