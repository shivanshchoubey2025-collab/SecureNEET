# SecureNEET — National Examination Management System

SecureNEET is a full-stack, production-ready, proctored examination platform designed for the National Eligibility cum Entrance Test for Undergraduates (NEET-UG).

The system features server-authoritative timer enforcement, continuous asynchronous answer autosaving, instantaneous scoring with negative marks (+4 / -1), All-India rankings, and newly implemented **State Topper** and **Gender Topper** leaderboards.

---

## 1. Project Overview

SecureNEET provides a reliable, secure computer-based test (CBT) environment inspired by NTA NEET portals.

Key highlights:
- **Three User Roles:** Administrator, Question Manager, and Student with strict backend RBAC.
- **Server-Authoritative Clock:** Examination deadlines are calculated and enforced on the server to prevent client-side clock tampering.
- **Resilient Periodic Autosave:** Answers are saved continuously to the database and recovered seamlessly upon page reload.
- **State Topper Feature:** Identifies and highlights the highest-performing student in each Indian State/UT with interactive state leaderboards.
- **Gender Topper Feature:** Recognizes top-performing students across voluntary demographic categories (Male, Female, Other), while honoring student privacy for undisclosed entries.
- **Audit Logging:** Administrative actions, logins, question edits, and submissions are tracked in a dedicated audit log.

---

## 2. Technology Stack

- **Backend Framework:** Python 3.13, Flask 3.1.1
- **Primary Database:** MySQL 8.0 (Relational schema via PyMySQL with connection pooling and transactions)
- **Zero-Dependency Fallback:** Built-in dual adapter supporting SQLite for immediate local development without a running MySQL daemon
- **Frontend:** Responsive HTML5, Custom High-Contrast CSS, Jinja2, Vanilla ES6 JavaScript (No Node build step required)
- **Security:** PBKDF2 Password Hashing, Session Fixation Protection, SQL Injection Prevention via Parameterized Queries, Security Headers (`X-Frame-Options`, `nosniff`, `X-XSS-Protection`)
- **Testing:** Pytest 9.1.1 test suite (17 automated tests covering Auth, Exam Lifecycle, Autosave, Scoring, Leaderboards, and RBAC Security)
- **Containerization:** Docker, Docker Compose, Gunicorn WSGI

---

## 3. Project Directory Structure

```text
SecureNEET/
├── app.py                      # Application factory and security header middleware
├── config.py                   # Environment configuration with secure defaults
├── db.py                       # Dual-adapter database engine (MySQL PyMySQL + SQLite fallback)
├── auth.py                     # Authentication utilities, password hashing, RBAC decorators
├── database.sql                # Canonical MySQL DDL schema + initial tables
├── seed_data.py                # Database seeder (Admin, Question Manager, Students, NEET questions)
├── Dockerfile                  # Production container definition
├── docker-compose.yml          # Web and MySQL 8.0 multi-container configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Documented environment variable template
├── .gitignore                  # Git ignore rules
├── migrations/
│   └── 001_state_gender_toppers.sql  # SQL migration for State & Gender Topper fields
├── services/
│   ├── exam_service.py         # Exam attempts, server deadline, autosave, and score calculation
│   ├── leaderboard_service.py  # Overall, State Topper, and Gender Topper algorithms with tie-breaking
│   └── audit_service.py        # System audit log tracker
├── routes/
│   ├── public.py               # Landing page, About, Available exams, Public leaderboards
│   ├── auth.py                 # Sign in, Student registration with State/Gender, Logout, Password reset
│   ├── admin.py                # Admin console, Student management, Exams, Questions, Audit logs
│   ├── student.py              # Candidate dashboard, Profile, Scorecard with subject breakdown
│   └── exam.py                 # Instructions, Live CBT interface, Autosave API, Timer API, Submit
├── templates/
│   ├── base.html               # Master layout with responsive navigation & flash alerts
│   ├── 403.html, 404.html, 500.html # Custom error pages
│   ├── public/                 # Index, About, Exams, Overall, State, and Gender topper templates
│   ├── auth/                   # Login, Registration, Password recovery templates
│   ├── student/                # Dashboard, Profile, Detailed Scorecard templates
│   ├── exam/                   # Pre-exam instructions, Live NEET exam portal
│   └── admin/                  # Dashboard, Students, Exams, Questions, Attempts, Audit logs
├── static/
│   ├── css/
│   │   ├── style.css           # Global modern responsive stylesheet
│   │   └── exam.css            # NEET CBT test screen & Question Palette stylesheet
│   └── js/
│       ├── main.js             # Alert auto-dismiss and confirmation handlers
│       └── exam.js             # Synchronized timer, question palette controller, and autosave
└── tests/
    ├── conftest.py             # In-memory test fixtures and client setup
    ├── test_auth.py            # Registration, login, and session test cases
    ├── test_exam.py            # Exam start, autosave, deadline enforcement, scoring test cases
    ├── test_leaderboards.py    # Overall, State Topper, Gender Topper, and tie-breaking test cases
    └── test_security.py        # RBAC privilege escalation and data isolation test cases
```

---

## 4. Prerequisites

- Python 3.10+ (Tested on Python 3.13)
- MySQL 8.0+ (Optional for local test runs, required for production)
- Docker & Docker Compose (Optional, for containerized deployments)

---

## 5. Local Installation

1. Navigate to the project directory:
   ```bash
   cd C:\Users\harsh\.gemini\antigravity\scratch\SecureNEET
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

---

## 6. Environment-Variable Setup

Create a `.env` file in the root directory by copying `.env.example`:
```bash
cp .env.example .env
```

Key variables:
- `SECRET_KEY`: Set to a strong random secret.
- `DB_TYPE`: `mysql` (use `sqlite` for offline development).
- `DB_HOST`: Hostname of MySQL (e.g., `localhost` or `mysql`).
- `DB_PORT`: `3306`.
- `DB_NAME`: `secureneet`.
- `DB_USER`: MySQL username.
- `DB_PASSWORD`: MySQL password.

---

## 7. MySQL Database Setup

1. Log into your MySQL console:
   ```bash
   mysql -u root -p
   ```

2. Create the database and dedicated user:
   ```sql
   CREATE DATABASE IF NOT EXISTS secureneet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER IF NOT EXISTS 'secureneet_user'@'localhost' IDENTIFIED BY 'your_password_here';
   GRANT ALL PRIVILEGES ON secureneet.* TO 'secureneet_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. Apply the canonical schema:
   ```bash
   mysql -u secureneet_user -p secureneet < database.sql
   ```

4. Seed the initial mock exams, questions, and accounts:
   ```bash
   python seed_data.py
   ```

---

## 8. Database Migration Instructions

If upgrading from an earlier version that lacked State Topper and Gender Topper fields:
```bash
mysql -u secureneet_user -p secureneet < migrations/001_state_gender_toppers.sql
```

The migration safely adds:
- `state` and `gender` columns to the `users` table.
- `state_rank` and `gender_rank` columns to the `examination_attempts` table.
- Non-destructive with safe defaults preserving existing records.

---

## 9. How to Run the Backend & Frontend

Start the application with Python:
```bash
python app.py
```

The application will be live at:
```
http://localhost:5000
```

Open any modern browser on desktop, tablet, or smartphone.

---

## 10. How to Execute Tests

Run the complete 17-test automated test suite:
```bash
python -m pytest tests -v
```

All 17 tests verify:
- Registration & Authentication
- Password Hashing & Salt Verification
- Server-side Timer Deadlines & Expiration
- Positive (+4) and Negative (-1) Scoring Calculations
- Duplicate Submission Prevention
- Overall Leaderboard and Deterministic Tie-breaking
- State Topper Rankings by State
- Gender Topper Rankings & Undisclosed Value Exclusion
- RBAC Privilege Escalation Prevention
- Cross-student Answer Tampering and Scorecard Isolation

---

## 11. Initial Provisioned Accounts

After running `python seed_data.py`, use the following accounts:

| Role | Email | Password | Access Privileges |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@secureneet.org` | `(set by seed_data.py)` | Full platform control, student toggling, exam publishing, audit logs, CSV export |
| **Question Manager** | `qm@secureneet.org` | `(set by seed_data.py)` | Question bank creation, subject editing, question preview |
| **Sample Student 1** | `aarav.sharma@example.com` | `(set by seed_data.py)` | Delhi Candidate, Male Topper |
| **Sample Student 2** | `ananya.iyer@example.com` | `(set by seed_data.py)` | Tamil Nadu Candidate, Female Topper (AIR 1) |

---

## 12. Production Build and Deployment via Docker Compose

Run the complete application and MySQL 8.0 cluster with persistent storage:
```bash
docker compose up -d --build
```

To inspect logs:
```bash
docker compose logs -f
```

To stop containers:
```bash
docker compose down
```

---

## 13. Security and Backup Recommendations

1. **Database Backups:**
   ```bash
   mysqldump -u secureneet_user -p secureneet > backup_$(date +%F).sql
   ```
2. **Reverse Proxy & HTTPS:** In production, place Nginx or Caddy in front of Gunicorn with automated Let's Encrypt SSL/TLS certificates.
3. **Session Secrets:** Ensure `SECRET_KEY` is rotated and stored securely in environment variables, never hardcoded.
4. **Rate Limiting:** Protect `/auth/login` and `/auth/register` behind standard reverse proxy rate limiters (e.g., 5 requests per minute per IP).

---

## 14. Common Errors and Solutions

| Error | Root Cause | Solution |
| :--- | :--- | :--- |
| `Can't connect to MySQL server (10061)` | MySQL service not running on host | Start MySQL (`net start mysql`), or let SecureNEET use the automatic local development fallback engine. |
| `Access Denied 403` | Logged-in user lacks required role | Sign in using an authorized account (`admin@secureneet.org` for admin tasks). |
| `Attempt expired` | Server-authoritative timer deadline lapsed | The attempt has been finalized automatically according to official examination rules. Check your scorecard on the dashboard. |
