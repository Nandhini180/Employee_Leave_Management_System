# LeaveHub

LeaveHub is a Django + Django REST Framework employee leave management system with:

- employee leave application and cancellation
- manager approval and rejection workflow
- automatic leave balance deduction and restoration
- weekend and holiday exclusion in leave day calculation
- yearly leave allocation management command
- Django admin, browser dashboard, and REST API
- Docker and docker-compose support

## Quick start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py allocate_yearly_leave --year 2026
python manage.py runserver
```

## Demo accounts

- Admin: `admin@leavehub.local` / `Admin@12345`
- Manager: `nandhini.v.2367@gmail.com` / `Demo@12345`
- Employee: `poorni@gmail.com` / `Demo@12345`
- Additional employees: `meera@gmail.com`, `arjun@gmail.com`, `kaviya@gmail.com` / `Demo@12345`

To recreate the full demo setup at any time:

```bash
python manage.py seed_demo_data
```

## Real email setup

By default, LeaveHub prints emails to the console for demos. To send real email notifications, set these environment variables before running the server:

```powershell
$env:EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST="smtp.gmail.com"
$env:EMAIL_PORT="587"
$env:EMAIL_HOST_USER="your-email@gmail.com"
$env:EMAIL_HOST_PASSWORD="your-app-password"
$env:EMAIL_USE_TLS="true"
$env:DEFAULT_FROM_EMAIL="your-email@gmail.com"
python manage.py runserver
```

For Gmail, use an App Password instead of your normal account password.

## Public holidays for 2026

The project includes a curated 2026 holiday dataset for India central gazetted holidays so leave day calculation can exclude them automatically.

Load them with:

```bash
python manage.py seed_public_holidays --year 2026
```

## Key URLs

- `/` dashboard
- `/admin/` Django admin
- `/api/leaves/`
- `/api/leaves/<id>/cancel/`
- `/api/manager/pending/`
- `/api/manager/<id>/approve/`
- `/api/manager/<id>/reject/`
- `/api/balance/`

## Docker

```bash
docker compose up --build
```

This starts:

- Django app at `http://localhost:8000`
- Adminer at `http://localhost:8080`

## Adminer with SQLite

To inspect the live SQLite database in a browser, open `http://localhost:8080` after `docker compose up --build`.

Use these Adminer login values:

- System: `SQLite`
- Server: leave blank
- Username: leave blank
- Password: `sqlite`
- Database: `/var/lib/sqlite/db.sqlite3`

The `db.sqlite3` file is mounted directly into the Adminer container, so what you see in Adminer matches the app database used by Django.

If you were already running the old Adminer container, rebuild it so the plugin is included:

```bash
docker compose down
docker compose up --build
```
