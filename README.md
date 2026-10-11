# JHCSC Competition Management System

A Django-based scoring and competition management platform for the J.H. Cerilles State
College Information Technology Department. It supports sports, talent, pageant, and
academic competitions with configurable scoring, judge panels, schedules, standings,
result approval, and public publication.

## Stack

| Layer        | Technology                                                   |
|--------------|--------------------------------------------------------------|
| Backend      | Django (installed: **6.0.8**)                                |
| Database     | **SQLite 3** (`db.sqlite3`) — see *Database* below            |
| Templates    | Django Templates                                              |
| Interactivity| HTMX (`django-htmx` middleware) + vanilla JS (`static/js`)    |
| Styling      | Tailwind CSS (Play CDN) + Google Fonts (Poppins / Open Sans)  |
| Admin theme  | django-jazzmin                                                |
| Env/deps     | `uv` (see `pyproject.toml`)                                   |

> **Note on Tailwind:** the UI currently loads Tailwind via the Play CDN
> (`<script src="https://cdn.tailwindcss.com">`) in `templates/base.html` and the
> auth/landing shells. This is convenient for development but **not recommended for
> production** (runtime compilation, external dependency). See *Known limitations*.

## Applications

`accounts`, `competitions`, `participants`, `teams`, `judges`, `scoring`, `sports`,
`eligibility`, `announcements`, `registrations`, `protests`, `audit`, `reports`.

## Getting started

```bash
# 1. Sync dependencies (uses uv; a .venv is present in this workspace)
uv sync

# 2. Apply migrations (safe — additive only; see Database)
uv run python manage.py migrate

# 3. Create an admin user
uv run python manage.py createsuperuser

# 4. Run the development server
uv run python manage.py runserver
```

The project's local `.venv` can be used directly instead of `uv run`:

```bash
.venv/Scripts/python.exe manage.py runserver     # Windows
.venv/bin/python manage.py runserver             # macOS/Linux
```

## Environment variables

All are optional in development (sensible defaults are provided).

| Variable               | Default                                    | Purpose                                   |
|------------------------|--------------------------------------------|-------------------------------------------|
| `DJANGO_SECRET_KEY`    | insecure dev key                           | Django secret key — **set in production** |
| `DJANGO_DEBUG`         | `True`                                     | Debug mode                                |
| `DJANGO_ALLOWED_HOSTS` | `*`                                        | Comma-separated host list                 |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.console.Email`  | Email backend (console prints to terminal)|
| `DEFAULT_FROM_EMAIL`   | `noreply@jhcsc-competition.local`          | Default sender address                    |

No `.env.example` exists yet; add one mirroring the table above when deploying.

## Database

The project is configured for **SQLite 3** (`scoring_system/settings.py`), not PostgreSQL.
To switch to PostgreSQL, change the `DATABASES` setting and provide connection env vars.

**Migrations & data safety**

- Always run `manage.py migrate` (additive). **Never** delete, reset, or truncate
  existing data. Do not run destructive commands against a live database.
- Test runs create and destroy an **isolated test database**; they never touch the real one.

## Running tests

```bash
uv run python manage.py test            # full suite (200 tests)
uv run python manage.py test <app>      # a single app, e.g. competitions
```

The suite covers scoring (including per-criterion weighting and score-verification
flows), rankings, authorization, registration review, scheduling, advancement, bracket
generation, standings/tie-breakers, public scoreboard visibility, CSV/PDF exports, and
data integrity. Test data is synthetic and lives only in the throwaway test database.

## User roles

Server-side permission checks are enforced in views, forms, and the API. Roles include
organizer/staff (manage competitions, participants, judges, schedules, approvals),
judge (submit evaluations), participant/team manager (register, view own results, submit
protests), and anonymous public viewers (read published results only). Role context is
exposed to templates via `accounts/context_processors.py`.

## UI / styling conventions

- Layout and navigation live in `templates/base.html` (sidebar + header + mobile drawer).
- Auth, login, register, and the landing page use standalone shells in
  `accounts/templates/accounts/` (`auth_base.html`, `login.html`, `register.html`,
  `landing_page.html`).
- Shared page blocks every page extends: `title`, `header_title`, `content`,
  `extra_head`, `extra_scripts`.
- Custom Tailwind tokens used across the app: colors `ink`, `campus`, `aqua`, `mist`;
  font `font-display`; shadow `shadow-soft`.
- Interactive helpers (modals, drawer, view toggles) are plain JS in `static/js/ui.js`.

## Known limitations

- **Tailwind via CDN** in `base.html` and the auth/landing shells; switch to a compiled
  Tailwind build for production.
- **SQLite** is the configured database; production deployments should use PostgreSQL.
- **Email** defaults to the console backend, so password-reset messages print to the
  terminal instead of being delivered.
- The UI was simplified for clarity: decorative gradients were flattened to solid brand
  tones, floating/blur decorations and hover-lift animations were removed, and shadows
  were reduced. No data or permissions were changed by that work.
- Earlier behavior remains intact: all schema changes made since then (competition
  kinds, cultural event types, per-competition medal points, criterion weights,
  `UNDER_REVIEW` registrations, `VERIFIED` scores, score-change history) shipped as
  **additive** migrations with safe defaults, so existing data keeps working. See
  `specs.md` §6 and `tasks.md` for the requirements-coverage pass.
