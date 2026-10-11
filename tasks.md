# Tasks — UI/UX Simplification

Status legend: ✅ done · ⏳ in progress · ⬜ not started

## Phase 1 — Inspection ✅

- ✅ Inspected project structure, apps, settings, DB config (SQLite), templates, static.
- ✅ Confirmed this is an existing, mature app (83 templates, 13 apps) — preserved
  architecture; no destructive changes.
- ✅ Established verification path: `.venv` present, Django 6.0.8 boots,
  `manage.py check` clean.

## Phase 2 — Design simplification ✅

- ✅ `templates/base.html`: flattened active-nav gradient, removed decorative circle +
  blurs, reduced sidebar/header shadows.
- ✅ Auth shells (`auth_base.html`, `login.html`, `register.html`) simplified.
- ✅ Landing page: removed floating-card animation and blur orbs; cleaned gaps.
- ✅ Global pass across all templates:
  - flattened all `bg-gradient-*` surfaces to solid tones,
  - `blur-2xl`/`blur-3xl` → removed,
  - `shadow-2xl` → `shadow-lg`,
  - `hover:-translate-y-*` → `hover:shadow-md`,
  - `duration-300` → `duration-150`.

## Phase 3 — Regression repair ✅

- ✅ Detected and repaired one template tag my regex had clipped
  (`competition_list.html` line 51: `{% endif %}` opening brace).
- ✅ Verified no other template has unbalanced `{%`/`%}` or orphaned `endfor`/`endif`.
- ✅ Re-pointed the results-page tab JS and settings toggle-switch to the new flat
  active classes so interactive state still highlights.

## Phase 4 — Verification ✅

- ✅ `manage.py check` → no issues.
- ✅ All 83 templates compile with 0 errors.
- ✅ `manage.py test competitions` → 8 tests, OK (fixes the one previously erroring test).
- ✅ Full suite `manage.py test` → green.

### Full-suite result

- Now **200 tests, all passing** (170 after the UI pass + 30 added by the
  requirements-coverage pass below).

## Phase 5 — Documentation ✅

- ✅ `README.md` — setup, env vars, DB, tests, roles, UI conventions, limitations.
- ✅ `specs.md` — architecture, change scope, verification, limitations.
- ✅ `tasks.md` — this file.

## Not in scope (unchanged, intentionally)

- No model/migration/data changes.
- No scoring, ranking, advancement, permission, or API changes.
- Tailwind remains on the CDN; SQLite/SQLite→PostgreSQL and compiled-Tailwind work are
  documented as future improvements, not simulated here.

---

# Tasks — Requirements Coverage Pass (2026-10-11)

This pass closed the seven remaining gaps between the system and the 21-module
requirements document, keeping all migrations strictly additive.

## Phase 1 — Registration review workflow ✅

- ✅ New `UNDER_REVIEW` status on `EventRegistration` (+ additive migration).
- ✅ `start_review()` service, "Start Review" action in the review queue and view,
  sky-colored badges, finalized registrations locked from further changes.

## Phase 2 — Configurable medal points ✅

- ✅ Per-competition `gold_points` / `silver_points` / `bronze_points` fields
  (defaults 10/5/3) flowed through the tally via `medal_points_for()`; inputs on
  the create/edit competition forms.

## Phase 3 — Cultural events & criterion weights ✅

- ✅ `Competition.Kind` (Sports/Cultural/Mixed) and `CulturalEventType`
  (dance, singing, quiz bee, …) selectable on both competition forms.
- ✅ `Criterion.weight_percentage`; when any criterion is weighted, round totals
  become `Σ average × weight%` (opt-in — all-zero weights keep the legacy sum).
  Weight inputs added to create-competition, create-round, and the (new)
  criteria editor on the edit-round page.

## Phase 4 — Score history & result approval ✅

- ✅ Immutable `ScoreChangeLog` model (+ migration) recording draft edits,
  submissions, verifications, and cleared verifications.
- ✅ `VERIFIED` score status counted everywhere `SUBMITTED` is
  (`COUNTED_STATUSES`); management can verify/clear-verify a round from the
  round-results page; paginated score-history view per competition/round.

## Phase 5 — Public live scoreboard ✅

- ✅ Anonymous spectators can watch `/competitions/<id>/scoreboard/` while the
  competition is ACTIVE or once results are published; before that a locked
  card with a sign-in link is shown (management/judges still see the board).

## Phase 6 — Reports ✅

- ✅ New CSV exports: judge scoring sheet and weighted standings (per round +
  overall) per competition, linked from the Reports home.

## Phase 7 — Admin dashboard widgets ✅

- ✅ Upcoming matches, current champions (top of each active competition's
  weighted standings), and overall medal standings widgets.

## Phase 8 — Safety & verification ✅

- ✅ Repaired latent bug: `edit_round` used to delete every criterion when the
  round-edit modal posted no criterion fields; criteria now persist unless the
  payload explicitly manages them.
- ✅ Repaired broken HTML attributes left by the earlier regex pass
  (`base.html` user menu, `round_results.html` avatar).
- ✅ All migrations additive; applied with `manage.py migrate`; `check` clean.
- ✅ New tests: 30 (scoring 21, competitions 6, registrations 3).

## Phase 9 — Documentation ✅

- ✅ `README.md`, `specs.md`, `tasks.md` updated for this pass.

