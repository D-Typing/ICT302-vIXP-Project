# vIXP (Virtual Internet Exchange Point)

University capstone project for simulating an Internet Exchange Point workflow with:

- Django
- Tailwind CSS
- PostgreSQL

This README explains how to run the project locally, create an admin superuser, test public registration, and check pending registration requests directly in PostgreSQL.

## 1. Prerequisites

- Windows PowerShell
- Python 3.12+ installed and available as `py`
- PostgreSQL 17 installed (default path used in this README):
  `C:\Program Files\PostgreSQL\17\bin`

## 2. Project Setup

From project root:
Create and activate virtual environment:

```powershell
py -m venv venv
.\venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## 3. Environment Configuration

The project reads local environment variables from `.env`.
Current expected values:

```env
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=vixp
POSTGRES_USER=vixp_user
POSTGRES_PASSWORD=J0BrXDQU6kimMpgp0AMigCuhlabCTOMF
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=55432
```

## 4. Start PostgreSQL (Project-Local Cluster)

This project uses a local PostgreSQL data directory: `.postgres-data`.

### If `.postgres-data` already exists

Start PostgreSQL (keep this terminal open):

```powershell
& "C:\Program Files\PostgreSQL\17\bin\postgres.exe" -D ".postgres-data" -p 55432 -c "listen_addresses=127.0.0.1"
```

### If `.postgres-data` does not exist (first-time init)

```powershell
Set-Content -Path ".pgpass.tmp" -Value "J0BrXDQU6kimMpgp0AMigCuhlabCTOMF"
& "C:\Program Files\PostgreSQL\17\bin\initdb.exe" -D ".postgres-data" -U vixp_user --pwfile=".pgpass.tmp" --auth-host=scram-sha-256 --auth-local=trust -E UTF8 --locale=C
Remove-Item ".pgpass.tmp"
```

Then start PostgreSQL using the command above.

## 5. Run Django

Open a second terminal in the same project folder:

```powershell
go to project root directory
.\venv\Scripts\activate
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

App URLs:

- Register: `http://127.0.0.1:8000/register/`
- Login: `http://127.0.0.1:8000/login/`
- Admin: `http://127.0.0.1:8000/admin/`

## 6. Create Admin Superuser (For Testing Login/Admin)

In the Django terminal:

```powershell
python manage.py createsuperuser
```

Enter username/email/password when prompted.

Then log in at:

`http://127.0.0.1:8000/admin/`

## 7. Test Registration Workflow

1. Open `http://127.0.0.1:8000/register/`
2. Submit a registration application
3. Confirm behavior:
   - user is created as `is_active=False`
   - registration status is `pending`
4. Log into admin and approve/reject from `Participant Registrations`

On approval, linked user account is activated.

## 8. View Pending Requests in PostgreSQL (Terminal)

Set password for `psql` session:

```powershell
$env:PGPASSWORD="J0BrXDQU6kimMpgp0AMigCuhlabCTOMF"
```

Check all registrations (latest first):

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h 127.0.0.1 -p 55432 -U vixp_user -d vixp -c "SELECT pr.id, pr.organisation_name, pr.asn, pr.status, u.email, pr.submitted_at FROM pages_participantregistration pr JOIN pages_user u ON u.id = pr.user_id ORDER BY pr.submitted_at DESC;"
```

Check only pending registrations:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h 127.0.0.1 -p 55432 -U vixp_user -d vixp -c "SELECT pr.id, pr.organisation_name, pr.asn, u.email, pr.submitted_at FROM pages_participantregistration pr JOIN pages_user u ON u.id = pr.user_id WHERE pr.status = 'pending' ORDER BY pr.submitted_at DESC;"
```

## 9. Stop Services

- Stop Django server: `Ctrl + C` in Django terminal
- Stop PostgreSQL server: `Ctrl + C` in PostgreSQL terminal

## 10. Optional: Tailwind Watcher (If Needed)

If you want live Tailwind recompilation in development, open another terminal:

```powershell
go to project root directory
.\venv\Scripts\activate
python manage.py tailwind start
```
