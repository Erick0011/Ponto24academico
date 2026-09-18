# Ponto 24 Académico

> **Plataforma digital de materiais académicos para estudantes angolanos.**

[Website](https://ponto24academico.com) · [GitHub](https://github.com/Erick0011/Ponto24academico)

---

## 🇬🇧 English

### About

**Ponto 24 Académico** is a digital platform designed to centralize, organize, and improve access to academic materials for university students in Angola.

The project was built as a real-world web application, focusing not only on features, but also on **software architecture, data management, security, scalability, and production deployment**.

---

## The Problem

Academic materials such as exams, summaries, exercises, and study resources are frequently shared through WhatsApp groups and other informal channels.

This creates several problems:

* Materials become scattered across different groups.
* Older resources are difficult to find.
* Students may not know whether a file is relevant or useful before downloading it.
* Access often depends on being part of the right group or knowing the right people.
* Students who contribute materials receive little recognition for sharing them.
* There is no centralized structure for organizing materials by institution, course, subject, and academic year.

### The goal

Build a centralized platform where students can **discover, contribute, evaluate, and manage academic resources** in an organized environment.

---

## The Solution

Ponto 24 Académico organizes materials by:

**Institution → Course → Subject → Academic Year → Category**

Students can search and filter resources, preview information before downloading, rate materials, save favorites, and report inappropriate content.

The platform also uses a **credit-based contribution system**:

> Contribute approved materials → earn credits → use credits to download materials.

This creates an incentive for users to contribute to the platform instead of only consuming content.

---

# Core Features

### 📚 Academic Materials

* Upload PDF, DOCX, and image files.
* SHA-256 hash-based duplicate detection.
* Material moderation before publication.
* Search and filtering.
* Organization by institution, course, subject, academic year, and category.
* Hierarchical folder management.
* Ratings from 1–5 stars.
* Favorites.
* View and download counters.
* Content reporting.

### 🎮 Contribution & Gamification

* Credits earned through approved contributions.
* Credits spent when downloading materials.
* User levels based on credit balance.
* Contribution-based progression.

### 🔐 Authentication & Accounts

* User registration and login.
* Mandatory email verification.
* Password recovery through expiring tokens.
* Secure password hashing.
* Session management.
* In-app notifications.

### 📧 Email System

Transactional emails for:

* Account verification.
* Welcome messages.
* Password recovery.
* Material approval/rejection.
* Application status.
* Other system notifications.

The platform also includes a marketing email system with:

* Sending throttling.
* Daily sending limits.
* Cancellation/unsubscribe support.
* `List-Unsubscribe` and `List-Unsubscribe-Post` headers.

### 🛠️ Administration

Administrative dashboard with:

* Platform KPIs.
* Audit logs.
* User management.
* Role management.
* Credit management.
* Material moderation.
* Category and folder management.
* Sponsored banner management.
* Application/volunteer management.
* Platform configuration.
* Bulk material import through CLI.

---

# Engineering

The project was designed as more than a CRUD application.

The architecture separates **HTTP handling, business logic, data access, configuration, and infrastructure concerns**, making the application easier to maintain and extend.

## Application Architecture

The application follows the **Application Factory** pattern.

```text
create_app()
    │
    ├── Configuration
    ├── Extensions
    ├── Blueprints
    ├── Error Handlers
    └── Application Hooks
```

Routes are organized using Flask Blueprints:

```text
app/
├── routes/
│   ├── auth.py
│   ├── main.py
│   ├── materiais.py
│   ├── admin.py
│   └── notificacoes.py
│
├── models/
├── services/
├── utils/
├── templates/
└── static/
```

### Why this architecture?

Instead of placing all logic inside route handlers, the application separates responsibilities.

```text
Request
   ↓
Route / Blueprint
   ↓
Service Layer
   ↓
SQLAlchemy Models
   ↓
Database
```

This keeps routes relatively thin and allows business logic to be reused by different parts of the application.

---

# Service Layer

Business logic is organized inside `app/services/`.

Examples include:

```text
services/
├── upload
├── email
├── credits
├── notifications
├── tokens
└── marketing
```

This separation is particularly useful for operations such as:

* Processing uploads.
* Sending emails.
* Managing credits.
* Creating notifications.
* Handling authentication tokens.
* Running email campaigns.

The goal is to avoid turning route handlers into large blocks of business logic.

---

# Database

The application uses **SQLAlchemy** as its ORM.

### Development

```text
SQLite
```

SQLite keeps local development simple and requires no external database server.

### Production

```text
PostgreSQL
```

PostgreSQL is used in production for a more robust relational database environment.

Database schema changes are managed through:

```text
Flask-Migrate
        ↓
     Alembic
```

This allows schema changes to be version-controlled and applied consistently across environments.

---

# File Storage

Academic materials are separated from the application's relational data.

The application supports:

### Local storage

Useful for development:

```text
app/static/uploads/
```

### Cloud storage

Production environments can use:

```text
Cloudflare R2
        ↓
S3-compatible API
        ↓
boto3
```

This prevents the application database from becoming responsible for storing large binary files and provides persistent storage independently from the application server.

---

# File Integrity & Duplicate Detection

Uploaded materials are processed using **SHA-256 hashing**.

Conceptually:

```text
File
 ↓
SHA-256
 ↓
Hash
 ↓
Duplicate check
```

This allows the system to identify identical files before unnecessarily storing duplicate content.

---

# Security

Security was considered at both the application and HTTP layers.

### Application security

* CSRF protection with Flask-WTF.
* Strong password policy.
* Secure password hashing.
* Session security.
* Email verification.
* Expiring password-reset tokens.
* Rate limiting.
* Honeypot protection on public forms.

### HTTP security

The application configures security headers including:

* Content Security Policy (CSP).
* `X-Frame-Options`.
* `X-Content-Type-Options`.
* `Referrer-Policy`.
* HTTP Strict Transport Security (HSTS).

### Production sessions

Secure cookies are enabled in production and HTTPS is required for secure session handling.

---

# Email Campaign Protection

The marketing system was designed with operational limits instead of sending an unlimited number of emails at once.

Example configuration:

```env
MARKETING_INTERVAL_SECONDS=3
MARKETING_DAILY_LIMIT=300
```

This provides:

* Sending throttling.
* Daily limits.
* Campaign cancellation.
* Unsubscribe support.

The goal is to reduce the risk of overwhelming the SMTP provider or damaging sender reputation.

---

# CLI & Management Commands

The application includes a custom management interface through `manage.py`.

Examples:

```bash
# Seed base categories
flask --app manage.py seed-db

# Create/promote administrator
flask --app manage.py criar-admin <email> <password>

# Test email configuration
flask --app manage.py testar-email <recipient>

# Preview bulk import
flask --app manage.py importar-lote ./pasta --dry-run

# Bulk import
flask --app manage.py importar-lote ./pasta \
    --auto-aprovar \
    --ano-letivo "2024/2025"
```

Database migrations:

```bash
flask --app manage.py db migrate -m "description"
flask --app manage.py db upgrade
```

---

# Production

The application can be served using **Gunicorn**:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

Production configuration supports:

* PostgreSQL.
* Cloudflare R2.
* SMTP.
* HTTPS.
* Secure cookies.
* Environment-based configuration.
* Gunicorn.

Sensitive configuration is provided through environment variables rather than being hard-coded into the repository.

---

# Configuration

Create the environment file:

```bash
cp .env.example .env
```

Important variables include:

```env
SECRET_KEY=
DATABASE_URL=

MAIL_SERVER=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

R2_ENDPOINT=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=

MAX_CONTENT_LENGTH_MB=
MARKETING_INTERVAL_SECONDS=
MARKETING_DAILY_LIMIT=
```

The production environment refuses insecure default secret configuration.

---

# Project Structure

```text
Ponto24academico/
│
├── app/
│   ├── __init__.py
│   │
│   ├── models/
│   │   └── ...
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── materiais.py
│   │   ├── admin.py
│   │   └── notificacoes.py
│   │
│   ├── services/
│   │   ├── upload
│   │   ├── email
│   │   ├── credits
│   │   ├── notifications
│   │   ├── tokens
│   │   └── marketing
│   │
│   ├── utils/
│   │
│   ├── static/
│   │   ├── css/
│   │   ├── img/
│   │   └── uploads/
│   │
│   └── templates/
│
├── config/
│   └── settings.py
│
├── migrations/
│
├── docs/
│   ├── TESTES.md
│   └── PONTO24_DOCUMENTACAO_TECNICA.pdf
│
├── manage.py
├── run.py
├── wsgi.py
├── requirements.txt
└── .env.example
```

---

# Tech Stack

| Layer                | Technology                          |
| -------------------- | ----------------------------------- |
| Language             | Python 3.10+                        |
| Backend              | Flask 3                             |
| ORM                  | SQLAlchemy                          |
| Database             | PostgreSQL / SQLite                 |
| Migrations           | Flask-Migrate / Alembic             |
| Authentication       | Flask-Login                         |
| Forms & CSRF         | Flask-WTF                           |
| Rate Limiting        | Flask-Limiter                       |
| File Storage         | Local Storage / Cloudflare R2       |
| Object Storage SDK   | boto3                               |
| Image Processing     | Pillow                              |
| Frontend             | Jinja2 + Bootstrap 5.3 + JavaScript |
| Web Server           | Gunicorn                            |
| Database Production  | PostgreSQL                          |
| Development Database | SQLite                              |

---

# Local Development

### Requirements

* Python 3.10+
* pip
* Git

### Clone

```bash
git clone https://github.com/Erick0011/Ponto24academico.git
cd Ponto24academico
```

### Virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```powershell
venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
```

Generate a secure secret:

```bash
python -c "import secrets; print(secrets.token_hex(24))"
```

Add it to `.env`.

### Initialize database

```bash
flask --app manage.py db upgrade
flask --app manage.py seed-db
```

### Create administrator

```bash
flask --app manage.py criar-admin admin@example.com StrongPassword123
```

### Run

```bash
python run.py
```

The application will be available at:

```text
http://localhost:5000
```

---

# Testing

The repository includes a manual functional testing checklist with **200+ test cases** covering different stages of development.

```text
docs/TESTES.md
```

The technical documentation also provides a deeper explanation of the application's modules, architecture, services, and design decisions.

```text
docs/PONTO24_DOCUMENTACAO_TECNICA.pdf
```

---

# Roadmap

* [x] Core academic material platform
* [x] Authentication
* [x] Material moderation
* [x] Credit system
* [x] Administrative dashboard
* [x] Audit logging
* [x] Hierarchical folder system
* [x] Automated application emails
* [x] Marketing email infrastructure
* [x] Security hardening
* [x] Production deployment preparation
* [ ] REST API
* [ ] Automated test suite
* [ ] Mobile application
* [ ] Advanced recommendation/search features
