# Azure VM Deployment

This deploy keeps the app private on the VM. Nginx listens on `127.0.0.1:8080`, FastAPI listens on `127.0.0.1:8000`, and you access the UI through an SSH tunnel.

## 1. Connect

From Windows PowerShell:

```powershell
ssh extapp@40.89.138.90
```

## 2. Install OS Dependencies

Run on the VM:

```bash
sudo apt-get update
sudo apt-get install -y git nginx python3 python3-venv python3-pip curl ca-certificates
```

Install Node.js 22 for Vite 7:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version
npm --version
```

## 3. Verify Ollama

Run on the VM:

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

The model list should include:

```text
qwen3-vl:235b-cloud
```

## 4. Clone Or Update App

First deploy:

```bash
sudo mkdir -p /opt/profile-extraction
sudo chown -R extapp:extapp /opt/profile-extraction
git clone https://github.com/elhossam7/to.git /opt/profile-extraction
cd /opt/profile-extraction
```

Future updates:

```bash
cd /opt/profile-extraction
git pull origin main
```

## 5. Configure Data And Environment

Run on the VM:

```bash
sudo mkdir -p /data/inbox /data/profiles
sudo chown -R extapp:extapp /data
sudo cp /opt/profile-extraction/deploy/profile-extraction.env.example /etc/profile-extraction.env
sudo chown root:root /etc/profile-extraction.env
sudo chmod 0644 /etc/profile-extraction.env
```

Confirm `/etc/profile-extraction.env` contains:

```text
DATA_DIR=/data
OLLAMA_URL=http://127.0.0.1:11434/api/generate
OLLAMA_MODEL=qwen3-vl:235b-cloud
OLLAMA_TIMEOUT=300
OLLAMA_STREAM=true
CORS_ORIGIN=http://127.0.0.1:8080
```

## 6. Install Backend And Test

Run on the VM:

```bash
cd /opt/profile-extraction
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest backend/tests
```

## 7. Build Frontend

Run on the VM:

```bash
cd /opt/profile-extraction/frontend
npm install
npm run build
```

## 8. Enable FastAPI Service

Run on the VM:

```bash
sudo cp /opt/profile-extraction/deploy/profile-extraction.service /etc/systemd/system/profile-extraction.service
sudo systemctl daemon-reload
sudo systemctl enable --now profile-extraction
sudo systemctl status profile-extraction --no-pager
```

Useful service commands:

```bash
sudo journalctl -u profile-extraction -f
sudo systemctl restart profile-extraction
```

## 9. Enable Nginx

Run on the VM:

```bash
sudo cp /opt/profile-extraction/deploy/nginx-profile-extraction.conf /etc/nginx/sites-available/profile-extraction
sudo ln -sf /etc/nginx/sites-available/profile-extraction /etc/nginx/sites-enabled/profile-extraction
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Smoke Test On VM

Run on the VM:

```bash
curl http://127.0.0.1:8000/status
curl -I http://127.0.0.1:8080
```

The status response should include:

```json
"ollama_reachable": true
```

## 11. Open The UI Through SSH Tunnel

From Windows PowerShell:

```powershell
ssh -L 8080:127.0.0.1:8080 extapp@40.89.138.90
```

Keep that terminal open, then visit:

```text
http://127.0.0.1:8080
```

## 12. End-To-End Check

Upload one or more `.txt` files for the same person in the UI, then verify on the VM:

```bash
ls -la /data/profiles
tail -n 20 /data/audit.log
```

You should see queued, started, and done events in the UI and one JSON profile under `/data/profiles` for the upload batch.

## Update Procedure

Run on the VM after pushing changes to `main`:

```bash
cd /opt/profile-extraction
git pull origin main
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
sudo systemctl restart profile-extraction
sudo systemctl reload nginx
curl http://127.0.0.1:8000/status
```
