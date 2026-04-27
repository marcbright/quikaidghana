# QuickAid Ghana

QuickAid Ghana is a Django web app for civic safety and utility intelligence: incident reporting, live map, SOS contacts, dashboard analytics, and a local keyword assistant.

## Features

- Incident reporting with geo pin picker (search, click map, current location)
- Live map with category markers and hospitals
- Dashboard charts and operational metrics
- SOS quick-call cards (Police, Fire, Ambulance, ECG, Water)
- Feedback/contact form persisted to `Feedback`
- Built-in Light/Dark theme system with saved preference

## Tech stack

- Python 3.12+
- Django 6
- PostgreSQL (recommended in production) or SQLite (local)
- WhiteNoise for static files
- Gunicorn for WSGI serving

## Local development

1. Create and activate virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment (optional for local):

```bash
cp .env.example .env
# Edit values as needed (DJANGO_DEBUG=1 for local)
```

4. Run migrations and create admin:

```bash
python manage.py migrate
python manage.py createsuperuser
```

5. Start server:

```bash
python manage.py runserver
```

## Deploy on Render (recommended)

This repository includes a ready-to-use `render.yaml` blueprint.

### Option A: Blueprint deploy (fastest)

1. Push your code to GitHub.
2. In Render dashboard, choose **New +** -> **Blueprint**.
3. Connect this repository and deploy.
4. Render will create:
   - `quickaid-ghana` web service
   - `quickaid-db` PostgreSQL instance

### Option B: Manual service setup

If you prefer manual setup, create a **Web Service** and **PostgreSQL** in Render and use the same values shown below.

### Build and start commands

- **Build command**

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

- **Start command**

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
```

### Required environment variables

Set these in Render service environment:

- `DJANGO_SECRET_KEY` (strong random value)
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=quickaid-ghana.onrender.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://quickaid-ghana.onrender.com`
- `DJANGO_SECURE_SSL_REDIRECT=1`
- `DJANGO_SECURE_HSTS_SECONDS=31536000`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1`
- `DJANGO_SECURE_HSTS_PRELOAD=1`
- `DJANGO_LOG_LEVEL=INFO`

Database variables (wire from Render Postgres values):

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE=require`
- `POSTGRES_CONN_MAX_AGE=60`

### One-time post-deploy commands

Open Render shell for the web service and run:

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Production deployment checklist

- [ ] Set `DJANGO_DEBUG=0`
- [ ] Set strong `DJANGO_SECRET_KEY`
- [ ] Set `DJANGO_ALLOWED_HOSTS`
- [ ] Set `DJANGO_CSRF_TRUSTED_ORIGINS` with `https://...`
- [ ] Configure PostgreSQL (`POSTGRES_*` vars)
- [ ] Ensure HTTPS / reverse proxy sets `X-Forwarded-Proto`
- [ ] Run migrations:
  ```bash
  python manage.py migrate
  ```
- [ ] Collect static files:
  ```bash
  python manage.py collectstatic --noinput
  ```
- [ ] Start app with Gunicorn:
  ```bash
  gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
  ```

## Health check

Use:

- `GET /healthz/` -> `{"status": "ok"}`

## Suggested GitHub repo structure

- Keep `venv/`, `.env`, `db.sqlite3`, and `staticfiles/` out of version control (already covered in `.gitignore`).
- Commit `media/.gitkeep` only (not uploaded media files).
- Keep secrets strictly in platform environment variables.

## Common commands

```bash
python manage.py check
python manage.py check --deploy
python manage.py test
python manage.py makemigrations
python manage.py migrate
```
