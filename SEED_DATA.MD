# Competrack — Seed Data & Test Credentials (`PALARO 2026`)

Organized reference of all seeded accounts, department teams, player rosters, sports competitions, static venues, and role-based access rules populated in the `competition_hub` database (`TIME_ZONE = Asia/Manila`).

---

## Quick Seed Commands

Implemented in `sports/management/commands/seed_palaro2026.py` (idempotent — safe to run multiple times without creating duplicates):

### Default Database (MySQL `competition_hub`)
```powershell
# Apply migrations first
.\.venv\Scripts\python.exe manage.py migrate

# Seed departments, 15 tournament managers, 4 department teams (60 players), and Basketball/Volleyball events
.\.venv\Scripts\python.exe manage.py seed_palaro2026

# Optional: clear old competitions/events/matches/registrations while preserving teams & rosters, then re-seed Basketball & Volleyball
.\.venv\Scripts\python.exe manage.py seed_palaro2026 --reset-competitions
```

### Local SQLite Fallback (`db.sqlite3`)
```powershell
$env:DB_ENGINE="sqlite"; .\.venv\Scripts\python.exe manage.py migrate
$env:DB_ENGINE="sqlite"; .\.venv\Scripts\python.exe manage.py seed_palaro2026
$env:DB_ENGINE="sqlite"; .\.venv\Scripts\python.exe manage.py seed_palaro2026 --reset-competitions
```

*(If no superuser exists when running `seed_palaro2026` on a fresh database, it automatically creates `admin` / `Admin2026!` and `safes_manager` / `SafesManager2026!` for SAFES – BULLS.)*

---

## 1. Department Team Managers & Approved Teams

All four official department teams are **Approved** and linked to the active sports categories. Once a department has an approved team, it is automatically locked from re-selection on new team registrations.

| Department | Team Name | Team ID | Status | Roster Size | Manager Name | Username | Password |
|---|---|---|---|---|---|---|---|
| **SAFES** | **BULLS** | `7` | Approved | 15 players | Jamesil Maputi *(existing)* | `jamesilmaputi65@gmail.com` | *(existing password)* |
| **STE** | **PHOENIX** | `8` | Approved | 15 players | Elena Villanueva | `ste_manager` | `SteManager2026!` |
| **SOCJE** | **DRAGON** | `9` | Approved | 15 players | Ramon Dela Cruz | `socje_manager` | `SocjeManager2026!` |
| **SCS** | **KITSUNE** | `10` | Approved | 15 players | Clarissa Navarro | `scs_manager` | `ScsManager2026!` |

### Seeded Departments
Managed by Admin at `/teams/departments/` (**Teams → Manage Departments**):

| Code | Full Name | Status |
|---|---|---|
| `SAFES` | School of Agriculture, Forestry and Environmental Studies | Active (Approved: `BULLS`) |
| `SOCJE` | School of Criminal Justice Education | Active (Approved: `DRAGON`) |
| `STE` | School of Teacher Education | Active (Approved: `PHOENIX`) |
| `SCS` | School of Computing Studies | Active (Approved: `KITSUNE`) |

---

## 2. PALARO 2026 Tournament Managers (Designated Scoring RBAC)

All **15 Tournament Managers** from the JHCSC PALARO 2026 schedule are seeded with role `TOURNAMENT_MANAGER`. Each Tournament Manager can only view and record match scores for their designated sports event(s) via `/sports/my-tournaments/`.

| Tournament Manager | Username | Password | Role | Designated Sports Event(s) |
|---|---|---|---|---|
| **Jezreel G. Bacalso** | `bacalso` | `Bacalso2026!` | Tournament Manager | Athletics (100m, 200m, 400m, 800m, 4x100m, 4x400m — Men & Women) |
| **Mary Juliet Doño** | `maryjuliet` | `Maryjuliet2026!` | Tournament Manager | Badminton (Men & Women) |
| **Allen Day Mori** | `mori` | `Mori2026!` | Tournament Manager | Baseball (Men) & Softball (Women) |
| **Nicaster Ambalong** | `ambalong` | `Ambalong2026!` | Tournament Manager | Basketball 5x5 & Basketball 3x3 (Men & Women) |
| **Carlo Giovanni D. Bascon** | `bascon` | `Bascon2026!` | Tournament Manager | Chess (Men & Women) |
| **Marjorey Cabigas** | `cabigas` | `Cabigas2026!` | Tournament Manager | Dance Sports (Latin, Modern Standard, Third Kind) & Powerdance |
| **Rob Kellean B. Barluado** | `barluado` | `Barluado2026!` | Tournament Manager | ESPORTS CODM & ESPORTS MLBB (Men & Women) |
| **Eric Lauron** | `lauron` | `Lauron2026!` | Tournament Manager | Frisbee (Mixed) |
| **Hannah Batucan** | `batucan` | `Batucan2026!` | Tournament Manager | Lawn Tennis (Men & Women) |
| **Vincent John Chatto** | `chatto` | `Chatto2026!` | Tournament Manager | Pickleball Doubles (Men, Women & Mixed) |
| **Niñobel Canencia** | `canencia` | `Canencia2026!` | Tournament Manager | Sepak Takraw (Men) |
| **Danny Lou C. Candia** | `candia` | `Candia2026!` | Tournament Manager | Table Tennis (Men) |
| **Helen Grace L. Elardo** | `elardo` | `Elardo2026!` | Tournament Manager | Table Tennis (Women) |
| **Zenon A. Matos, Jr.** | `matos` | `Matos2026!` | Tournament Manager | Volleyball (Men) |
| **Ronilo S. Bustamante** | `bustamante` | `Bustamante2026!` | Tournament Manager | Volleyball (Women) |

---

## 3. Seeded Sports Competitions & Events

Cleared old competitions, matches, and entries, and populated fresh **Basketball** and **Volleyball** sports competitions (while preserving all teams and rosters):

| Competition | Sports Event | Division | Required Players | Static Venue | Designated Tournament Manager |
|---|---|---|---|---|---|
| **JHCSC Intramural Basketball 2026** | Basketball - Men | Open · Male | 15 / team | `JHCSC Basketball Court` | Nicaster Ambalong (`ambalong`) |
| **JHCSC Intramural Basketball 2026** | Basketball - Women | Open · Female | 15 / team | `JHCSC Basketball Court` | Nicaster Ambalong (`ambalong`) |
| **JHCSC Intramural Volleyball 2026** | Volleyball - Men | Open · Male | 12 / team | `JHCSC Campus (Volleyball Court)` | Zenon A. Matos, Jr. (`matos`) |
| **JHCSC Intramural Volleyball 2026** | Volleyball - Women | Open · Female | 12 / team | `JHCSC Campus (Volleyball Court)` | Ronilo S. Bustamante (`bustamante`) |

*(Any additional Basketball 5x5 / 3x3 events created by Admin were also assigned to `ambalong`.)*

---

## 4. Populated Team Rosters (60 Players Total)

Every department team has **15 active players** (8 Male, 7 Female, Category `OPEN`, Jersey `#1–#15`).

### SAFES — BULLS (ID `7`)
| # | Name | Gender | Age | ID Number | Phone |
|---|---|---|---|---|---|
| 1 | Marco Villanueva | Male | 20 | `SAFES-2026-001` | `09171010001` |
| 2 | Rafael Mendoza | Male | 21 | `SAFES-2026-002` | `09171010002` |
| 3 | Gabriel Santos | Male | 19 | `SAFES-2026-003` | `09171010003` |
| 4 | Paolo Reyes | Male | 22 | `SAFES-2026-004` | `09171010004` |
| 5 | Miguel Bautista | Male | 20 | `SAFES-2026-005` | `09171010005` |
| 6 | Daniel Cruz | Male | 18 | `SAFES-2026-006` | `09171010006` |
| 7 | Joshua Aquino | Male | 21 | `SAFES-2026-007` | `09171010007` |
| 8 | Christian Navarro | Male | 20 | `SAFES-2026-008` | `09171010008` |
| 9 | Andrea Torres | Female | 19 | `SAFES-2026-009` | `09171010009` |
| 10 | Camille Ramos | Female | 20 | `SAFES-2026-010` | `09171010010` |
| 11 | Bianca Flores | Female | 21 | `SAFES-2026-011` | `09171010011` |
| 12 | Patricia Morales | Female | 18 | `SAFES-2026-012` | `09171010012` |
| 13 | Nicole Castillo | Female | 22 | `SAFES-2026-013` | `09171010013` |
| 14 | Katrina Dela Rosa | Female | 19 | `SAFES-2026-014` | `09171010014` |
| 15 | Sophia Lim | Female | 20 | `SAFES-2026-015` | `09171010015` |

### STE — PHOENIX (ID `8`)
| # | Name | Gender | Age | ID Number | Phone |
|---|---|---|---|---|---|
| 1 | Adrian Mercado | Male | 20 | `STE-2026-001` | `09172010001` |
| 2 | Kenneth Soriano | Male | 21 | `STE-2026-002` | `09172010002` |
| 3 | Jericho Alcantara | Male | 19 | `STE-2026-003` | `09172010003` |
| 4 | Vincent Pascual | Male | 22 | `STE-2026-004` | `09172010004` |
| 5 | Jerome Salcedo | Male | 20 | `STE-2026-005` | `09172010005` |
| 6 | Francis Ocampo | Male | 18 | `STE-2026-006` | `09172010006` |
| 7 | Carlo Magno | Male | 21 | `STE-2026-007` | `09172010007` |
| 8 | Bryan Tolentino | Male | 20 | `STE-2026-008` | `09172010008` |
| 9 | Clarisse Domingo | Female | 19 | `STE-2026-009` | `09172010009` |
| 10 | Hannah Velasco | Female | 20 | `STE-2026-010` | `09172010010` |
| 11 | Denise Aguilar | Female | 21 | `STE-2026-011` | `09172010011` |
| 12 | Alyssa Mariano | Female | 18 | `STE-2026-012` | `09172010012` |
| 13 | Trisha Panganiban | Female | 22 | `STE-2026-013` | `09172010013` |
| 14 | Jasmine Corpuz | Female | 19 | `STE-2026-014` | `09172010014` |
| 15 | Michelle Tan | Female | 20 | `STE-2026-015` | `09172010015` |

### SOCJE — DRAGON (ID `9`)
| # | Name | Gender | Age | ID Number | Phone |
|---|---|---|---|---|---|
| 1 | Dante Valdez | Male | 21 | `SOCJE-2026-001` | `09173010001` |
| 2 | Rodel Gutierrez | Male | 22 | `SOCJE-2026-002` | `09173010002` |
| 3 | Mark Anthony Perez | Male | 20 | `SOCJE-2026-003` | `09173010003` |
| 4 | Jayson Ferrer | Male | 19 | `SOCJE-2026-004` | `09173010004` |
| 5 | Arnel Padilla | Male | 21 | `SOCJE-2026-005` | `09173010005` |
| 6 | Renzo Cabrera | Male | 20 | `SOCJE-2026-006` | `09173010006` |
| 7 | Lester Manalo | Male | 18 | `SOCJE-2026-007` | `09173010007` |
| 8 | Noel Sarmiento | Male | 22 | `SOCJE-2026-008` | `09173010008` |
| 9 | Maricel Bernardo | Female | 19 | `SOCJE-2026-009` | `09173010009` |
| 10 | Angelica Enriquez | Female | 20 | `SOCJE-2026-010` | `09173010010` |
| 11 | Shiela Espinoza | Female | 21 | `SOCJE-2026-011` | `09173010011` |
| 12 | Kimberly Galang | Female | 18 | `SOCJE-2026-012` | `09173010012` |
| 13 | Rhea Javier | Female | 22 | `SOCJE-2026-013` | `09173010013` |
| 14 | Lorraine Robles | Female | 19 | `SOCJE-2026-014` | `09173010014` |
| 15 | Diana Serrano | Female | 20 | `SOCJE-2026-015` | `09173010015` |

### SCS — KITSUNE (ID `10`)
| # | Name | Gender | Age | ID Number | Phone |
|---|---|---|---|---|---|
| 1 | Ethan Sy | Male | 20 | `SCS-2026-001` | `09174010001` |
| 2 | Kyle Ong | Male | 21 | `SCS-2026-002` | `09174010002` |
| 3 | Nathaniel Chua | Male | 19 | `SCS-2026-003` | `09174010003` |
| 4 | Sean Go | Male | 22 | `SCS-2026-004` | `09174010004` |
| 5 | Caleb Co | Male | 20 | `SCS-2026-005` | `09174010005` |
| 6 | Ivan Yu | Male | 18 | `SCS-2026-006` | `09174010006` |
| 7 | Jared Lao | Male | 21 | `SCS-2026-007` | `09174010007` |
| 8 | Lucas Ang | Male | 20 | `SCS-2026-008` | `09174010008` |
| 9 | Chloe Uy | Female | 19 | `SCS-2026-009` | `09174010009` |
| 10 | Isabelle Dy | Female | 20 | `SCS-2026-010` | `09174010010` |
| 11 | Samantha Tiu | Female | 21 | `SCS-2026-011` | `09174010011` |
| 12 | Audrey Wee | Female | 18 | `SCS-2026-012` | `09174010012` |
| 13 | Mikaela Yap | Female | 22 | `SCS-2026-013` | `09174010013` |
| 14 | Rachelle See | Female | 19 | `SCS-2026-014` | `09174010014` |
| 15 | Erica Que | Female | 20 | `SCS-2026-015` | `09174010015` |

---

## 5. PALARO 2026 Static Sports Catalog

Defined in `sports/services.py` (`PALARO_STATIC_EVENTS`) and available via dropdown when creating a Sports competition. Selecting an event auto-fills its static venue, match duration, required players per team, point system, and designated Tournament Manager.

| Static Event | Required Players | Static Venue | Duration | Points (1st/2nd/3rd) | Default Tournament Manager |
|---|---|---|---|---|---|
| Basketball 5x5 | 15 | JHCSC Basketball Court | 90 min | 10 / 7 / 5 | `ambalong` |
| Basketball 3x3 | 4 | JHCSC Basketball Court | 45 min | 10 / 7 / 5 | `ambalong` |
| Volleyball | 12 | JHCSC Campus (Volleyball Court) | 90 min | 10 / 7 / 5 | `matos` (M) / `bustamante` (W) |
| Sepak Takraw | 12 | JHCSC Campus Takraw Court | 90 min | 10 / 7 / 5 | `canencia` |
| ESPORTS MLBB | 6 | SCS ComLab1 | 60 min | 10 / 7 / 5 | `barluado` |
| ESPORTS CODM | 6 | SCS ComLab1 | 60 min | 10 / 7 / 5 | `barluado` |
| Badminton | 4 | Caridad Covered Court | 20 min | 8 / 6 / 4 | `maryjuliet` |
| Table Tennis | 4 | JHCSC Room - Table Tennis | 30 min | 8 / 6 / 4 | `candia` (M) / `elardo` (W) |
| Pickleball (Doubles) | 2 | Mango Drive Pickledrive | 45 min | 8 / 6 / 4 | `chatto` |
| Lawn Tennis | 4 | Dumingag Sports Complex Lawn Tennis Court | 45 min | 8 / 6 / 4 | `batucan` |
| Chess | 4 | JHCSC Library | 15 min | 6 / 5 / 4 | `bascon` |
| Baseball | 18 | JHCSC Campus Baseball Diamond | 120 min | 10 / 7 / 5 | `mori` |
| Softball | 18 | JHCSC Campus Softball Diamond | 120 min | 10 / 7 / 5 | `mori` |
| Frisbee | 15 | JHCSC Campus Grounds | 60 min | 10 / 7 / 5 | `lauron` |
| Athletics (100m / 200m / 400m / 800m) | 1 | JHCSC Campus Oval | 180 min | 6 / 5 / 4 | `bacalso` |
| Athletics (4x100m / 4x400m) | 4 | JHCSC Campus Oval | 180 min | 10 / 7 / 5 | `bacalso` |
| Dance Sports (Latin / Modern Standard / Third Kind) | 2 | JHCSC Function Hall | 60 min | 8 / 6 / 4 | `cabigas` |
| Powerdance | 50 | JHCSC Campus Grounds | 60 min | 15 / 12 / 10 | `cabigas` |

---

## 6. Role-Based Access Control (RBAC) Quick Reference

- **Administrator (`admin`)**:
  - Approves/rejects department teams (with sidebar counter badges on **Teams** and **Registrations**).
  - Manages Departments (`/teams/departments/`), Sports Competitions (static PALARO 2026 dropdown + tournament format), Auto-Match (`Team 1–4` slot assignment + automatic conflict-free scheduling at static venues), and User Access Control (modal-driven at `/users/`).
  - Verifies submitted team rosters in read-only mode (cannot register players or build team rosters).
- **Team Manager (`TEAM_MANAGER`)**:
  - Submits department team registration (locked once a department is approved).
  - Manages players **strictly for their own approved team** (cannot view or assign players from other teams or unassigned global pools), assigns players to sports events up to `players_per_event`, and submits final rosters.
- **Tournament Manager (`TOURNAMENT_MANAGER`)**:
  - Lands on **My Tournaments** (`/sports/my-tournaments/`).
  - Can view schedules, brackets, standings, and **record/update match scores strictly for their designated sports event(s)**. All other events and admin views return `403 Forbidden`.
