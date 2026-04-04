# Running the Application

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Node.js 20+ and npm (for local frontend development only)
- Python 3.12+ and pip (for local backend development only)

---

## Option 1 — Docker Compose (recommended)

This starts all services (PostgreSQL, Redis, backend, Celery workers, and frontend) with a single command.

### 1. Copy the environment file

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | What to set |
|---|---|
| `DJANGO_SECRET_KEY` | Any random string of 50+ characters |
| `POSTGRES_USER` | e.g. `contract_user` |
| `POSTGRES_PASSWORD` | Any strong password |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required for the email organiser) |

All other defaults in `.env.example` work out of the box for local development.

### 2. Start all services

```bash
docker compose up --build
```

The first build takes a few minutes while Docker downloads base images and installs dependencies. Subsequent starts are fast.

### 3. Run database migrations (first run only)

In a second terminal, once the `backend` container is healthy:

```bash
docker compose exec backend python manage.py migrate
```

Optionally load fixtures (sample data):

```bash
docker compose exec backend python manage.py loaddata fixtures/*.json
```

### 4. Access the application

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend API (Django) | http://localhost:8000/api/ |
| API schema (Swagger) | http://localhost:8000/api/docs/ |
| API schema (ReDoc)   | http://localhost:8000/api/redoc/ |
| Django admin         | http://localhost:8000/admin/ |

### Stopping

```bash
docker compose down          # stop containers, keep database volume
docker compose down -v       # stop and delete database volume (full reset)
```

---

## Option 2 — Local development (without Docker)

Use this if you want faster hot-reload or need to debug a single service.

### Backend

**Requirements:** Python 3.12+, a running PostgreSQL 16 instance, a running Redis 7 instance.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements/development.txt
```

Set environment variables (or create a `.env` in the project root and export them):

```bash
export DJANGO_SETTINGS_MODULE=config.settings.development
export DB_USER=your_actual_postgres_username
export DB_PASSWORD=your_actual_postgres_password
export DATABASE_URL=postgresql://<user>:<password>@localhost:5432/contract_mgmt
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/2
# export DJANGO_SECRET_KEY=<your-secret-key>
```

Run migrations and start the server:

```bash
python manage.py makemigrations accounts
python manage.py makemigrations projects
python manage.py makemigrations contracts
python manage.py makemigrations notifications
python manage.py makemigrations chat
python manage.py makemigrations email_organiser
python manage.py makemigrations dashboard

python manage.py migrate

# Load fake data
python manage.py loaddata fixtures/users.json fixtures/initial_data.json

python manage.py shell
    - from accounts.models import User
    - u = User.objects.get(email='alice.manager@example.com')
    - u.set_password('password123') 
    - u.save()

python manage.py runserver          # or: daphne -p 8000 config.asgi:application
```

Start Celery workers in separate terminals:

```bash
celery -A config worker -l info     # async task worker
celery -A config beat -l info       # scheduled task runner
```

### Frontend

**Requirements:** Node.js 20+, npm.

```bash
cd frontend
npm install
```

Create a `.env.local` file (or rely on the root `.env`):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

Start the development server:

```bash
npm run dev
```

The app is available at http://localhost:3000.

---

## Running tests

### Backend

```bash
cd backend
pytest                                       # all tests
pytest --cov=. --cov-fail-under=80          # with coverage gate (80% required)
```

### Frontend

```bash
cd frontend
npm run lint            # ESLint
npm run type-check      # TypeScript (tsc --noEmit)
npm test                # Jest unit + integration tests
npm run test:e2e        # Playwright end-to-end tests (requires a running dev server)
```

---

## Services overview

| Container | Role | Port |
|---|---|---|
| `postgres` | PostgreSQL 16 database | 5432 |
| `redis` | Broker for Celery + Django Channels | 6379 |
| `backend` | Django + Daphne (ASGI, handles HTTP + WebSockets) | 8000 |
| `celery` | Async task worker | — |
| `celery-beat` | Periodic task scheduler | — |
| `frontend` | Next.js dev server | 3000 |
