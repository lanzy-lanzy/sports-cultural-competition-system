# Specifications — JHCSC Competition Management System

This document describes the current architecture and the scope of the UI/UX
simplification work. It reflects the repository as verified, not an aspiration.

## 1. Architecture

- **Framework:** Django (installed version 6.0.8), server-rendered Django Templates.
- **Database:** SQLite 3 (`db.sqlite3`).
- **Interactivity:** HTMX for partial updates (`django_htmx.middleware.HtmxMiddleware`),
  plus vanilla JavaScript helpers in `static/js/ui.js` and `static/js/scoring-panel.js`.
- **Styling:** Tailwind CSS via Play CDN with a small custom token set; Google Fonts.
- **Admin:** django-jazzmin (admin theming only; not the primary UI).
- **Apps:** accounts, competitions, participants, teams, judges, scoring, sports,
  eligibility, announcements, registrations, protests, audit, reports.

### Template contract

Every page extends `templates/base.html` (or `accounts/auth_base.html` for auth pages)
and may fill these blocks:

| Block          | Purpose                                   |
|----------------|-------------------------------------------|
| `title`        | Document `<title>`                        |
| `header_title` | In-app header heading                     |
| `content`      | Main page body                            |
| `extra_head`   | Extra `<head>` content (e.g. page CSS)    |
| `extra_scripts`| Extra JS after content                    |

`accounts/context_processors.py` injects role context (`account_role`,
`account_role_display`, `can_manage`, `is_account_admin`, `active_nav`) used for
server-rendered navigation and gating.

## 2. UI/UX simplification scope

The requested change was to simplify the interface. This was done **strictly in the
presentation layer** — no models, views, scoring logic, URLs, permissions, or data were
modified.

### Design changes applied

- **Flattened decorative gradients → solid brand tones.** Every `bg-gradient-to-*`
  surface was converted to a flat fill using its primary ("from") color so the palette
  stays consistent. Examples: `from-campus to-aqua` → `bg-campus`,
  `from-cyan-600 to-teal-500` → `bg-cyan-700`, medal/ribbon gradients → flat colors.
- **Removed decorative blur orbs** (`blur-2xl` / `blur-3xl`) and the animated floating
  card keyframes on the landing page.
- **Calmmed shadows:** `shadow-2xl` → `shadow-lg`; active nav uses a subtle fill instead
  of a gradient + glow.
- **Removed hover-lift animations** (`hover:-translate-y-*`) in favor of a light
  `hover:shadow-md` affordance, so cards no longer jump on hover.
- **Shortened slow transitions** (`duration-300` → `duration-150`) for snappier feedback.
- **Preserved accessibility:** `prefers-reduced-motion` handling retained; focus rings,
  ARIA attributes, labels, and semantic landmarks untouched.

### Functional guarantees

- All navigation links, role-gated menu items, and URL targets are unchanged.
- All forms, HTMX attributes, Alpine/vanilla-JS hooks (`openModal`, `closeModal`,
  `openDeleteComp`, view toggles, tab switching) continue to work.
- Active-tab and toggle-switch states were re-pointed to the new flat active classes so
  state highlighting still renders.

## 3. What was NOT changed

- Models, migrations, database schema, and existing data.
- Scoring, ranking, tie-breaker, or advancement logic.
- Views, forms, serializers, URLs, permissions, and validation.
- API contracts and response shapes.

## 4. Verification

- `manage.py check` → no issues.
- All 83 templates compile (`django.template` loader) with 0 errors.
- Full test suite passes — **200 tests, OK** (see `tasks.md` for the run results).

## 5. Known limitations

- Tailwind is loaded via CDN (not compiled); move to a build step for production.
- Database is SQLite; use PostgreSQL for production.
- Email uses the console backend by default (password-reset emails print to terminal).

## 6. Requirements coverage pass (2026-10-11)

Closing the gaps against the 21-module requirements document. All schema changes are
**additive migrations** with defaults that preserve legacy behavior.

- **Registrations:** `UNDER_REVIEW` status + `start_review()` service; finalized
  registrations are immutable from the review queue.
- **Competitions:** `kind` (Sports/Cultural/Mixed), `cultural_event_type` (dance,
  singing, quiz bee, …), per-competition `gold/silver/bronze_points` (defaults
  10/5/3), and `criterion.weight_percentage` (opt-in; all-zero keeps the legacy
  sum-of-averages scoring).
- **Scoring:** `Score.status` lifecycle DRAFT → SUBMITTED → VERIFIED with
  `COUNTED_STATUSES = (SUBMITTED, VERIFIED)` used by totals, rankings, and round
  results; immutable `ScoreChangeLog`; management-only `verify_round_scores` /
  `unverify_round_scores`; paginated `score_history` view; round-results page
  exposes verify/clear controls only to management.
- **Scoreboard:** public `/competitions/<id>/scoreboard/` — anonymous visitors see
  the live board while the competition is ACTIVE or once `show_results` is on;
  otherwise a locked card with a sign-in link renders (management and judges
  always see it).
- **Reports:** `export_judge_scores_csv` (per judge/criterion sheet) and
  `export_standings_csv` (weighted overall + per-round standings), linked from the
  Reports home.
- **Dashboard:** upcoming matches, current champions (top of each active
  competition's weighted standings), and overall medal standings widgets.
- **Safety fixes:** `edit_round` no longer deletes criteria when the round-edit
  modal posts no criterion payload; repaired two broken HTML attributes left by
  the earlier regex pass.
