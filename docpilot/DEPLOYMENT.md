# DocPilot — Production Deployment Guide

DocPilot can be deployed in three ways depending on your use case:

---

## 1. ☁️ Cloud Deployment (Render.com) — Free & Instant

Render can directly deploy DocPilot from your GitHub repository:

1. Push your code to GitHub.
2. Sign up / Log in to [Render](https://render.com).
3. Click **New +** → **Web Service**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml` or you can configure manually:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --workers 2 --threads 4 --timeout 120`
6. Add Environment Variables in Render dashboard:
   - `GEMINI_API_KEY`: Your Google Gemini API key (optional, has keyword fallback)
   - `OPENAI_API_KEY`: Your OpenAI API key (optional)
7. Click **Create Web Service**. Your app is live with free SSL HTTPS!

---

## 2. 🖥️ Local / Office Production Server (Windows / On-Premise)

For offices, clinics, or firms running on a local PC or Windows Server:

1. Open PowerShell or Command Prompt in `docpilot`:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the production Waitress server:
   ```bash
   python run_production.py
   ```
   Or simply double-click `run_production.bat`.
3. The server runs multi-threaded and is accessible to all computers on your local Wi-Fi / LAN via `http://<YOUR_LOCAL_IP>:5000`.

---

## 3. 🐳 Containerized Deployment (Docker)

To deploy using Docker or Docker Compose:

1. Build the Docker image:
   ```bash
   docker build -t docpilot .
   ```
2. Run the container:
   ```bash
   docker run -d -p 5000:5000 \
     -e GEMINI_API_KEY="your-key-here" \
     --name docpilot-app docpilot
   ```
3. Open `http://localhost:5000`.

---

## 📁 Persistent Storage Note

DocPilot writes filed documents to `./filed/` and uploads to `./uploads/`, and stores records in `docpilot.db`.
- When deploying to cloud hosts with ephemeral disks (like basic free Render containers), files reset on dyno restarts.
- For permanent cloud storage, attach a persistent disk volume to `/app/filed` or mount S3/Google Cloud Storage.
- For local/desktop deployment (Windows), all files permanently stay on your local disk in `filed/`.
