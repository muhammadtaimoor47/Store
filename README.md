# Derna FM — Inventory Management System

Flask + SQLite inventory web app with role-based access.

## Deploy on Render.com

1. Push this folder to a GitHub repo
2. Go to https://render.com → New → Web Service → connect your repo
3. Set these:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Add environment variables in Render dashboard:
   - `SECRET_KEY` → any random string
   - `SK_USERNAME` → storekeeper
   - `SK_PASSWORD` → your password
   - `DB_PATH` → `/data/inventory.db`
5. Add a Disk under "Disks": mount path `/data`, size 1GB
6. Deploy!

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Credentials

- **Viewer:** no login needed (read-only)
- **Storekeeper:** login with SK_USERNAME / SK_PASSWORD

