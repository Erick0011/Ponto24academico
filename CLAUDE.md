# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Ponto 24 Académico** — Flask web platform for Angolan students to share and download academic materials (exams, summaries, exercises). Materials go through a moderation queue before becoming public.

---

## Commands

### Development server
```bash
flask run
# or with debug explicitly off (to test error pages):
$env:FLASK_DEBUG="0"; flask run
```

### Database migrations
```bash
flask db migrate -m "description"   # generate migration
flask db upgrade                     # apply migrations
```

### CLI management (all via manage.py)
```bash
flask --app manage.py seed-db                          # create base categories
flask --app manage.py criar-admin <email> <password>   # create/promote admin
flask --app manage.py testar-email <recipient>         # send all 3 email types as test
flask --app manage.py importar-lote ./pasta --dry-run  # bulk import preview
flask --app manage.py importar-lote ./pasta --auto-aprovar --ano-letivo "2024/2025"
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### Required `.env` variables
```
FLASK_DEBUG=0
SECRET_KEY=<secure-random-key>
EMAIL_USER=<gmail-address>
EMAIL_PASS=<gmail-app-password>
DATABASE_URL=sqlite:///ponto24.db          # or postgresql://...
MAX_CONTENT_LENGTH_MB=20
```

---

## Architecture

### App factory & blueprints
`app/__init__.py` creates the Flask app via `create_app()`. Five blueprints are registered:

| Blueprint | Prefix | File |
|-----------|--------|------|
| `auth` | `/auth` | `app/routes/auth.py` |
| `main` | `/` | `app/routes/main.py` |
| `materiais` | `/materiais` | `app/routes/materiais.py` |
| `admin` | `/admin` | `app/routes/admin.py` |
| `notificacoes` | `/notificacoes` | `app/routes/notificacoes.py` |
| `comunidade` | `/comunidade` | `app/routes/comunidade.py` |

`__init__.py` also registers:
- `before_request` hook that enforces the 7-day email confirmation deadline — redirects to `/auth/email-nao-confirmado` after the deadline, except for a whitelist of auth endpoints.
- `context_processor` that injects `notif_nao_lidas` (int) and `dias_confirmacao` (int|None) into every template.
- `paginate_url(page)` as a Jinja2 global for building pagination URLs.

### Models (`app/models/`)

- **`User`** — `is_admin > is_moderador > normal`. Credit balance tracked as `creditos`. Gamification level derived from credits via `User.nivel` property (Novato → Expert).
- **`Material`** — three statuses: `STATUS_PENDENTE / STATUS_APROVADO / STATUS_REJEITADO`. Upload path stored relative to `UPLOAD_FOLDER`. SHA-256 hash in `ficheiro_hash` for duplicate detection. Multiple files uploaded together share a `grupo_upload` UUID.
- **`Notificacao`** — in-app only; three types defined as class constants.
- **`PesquisaLog`** — logged once per unique search term per page-1 visit, used for KPI.

### Services (`app/services/`)

- **`upload_service.py`** — `guardar_ficheiro()` saves to `materiais/{cat_slug}/{YYYY}/{MM}/{uuid}.ext`, calculates SHA-256, generates 300×300 thumbnail for images into a `thumbs/` subfolder. `thumbnail_path` property on `Material` mirrors this structure.
- **`tokens_service.py`** — `itsdangerous` HMAC tokens with separate salts for email confirmation (24h) and password recovery (1h).
- **`mail_service.py`** — pure SMTP via `smtplib`, no Flask-Mail. Reads `EMAIL_USER`/`EMAIL_PASS` or `MAIL_USERNAME`/`MAIL_PASSWORD`. Silently skips if SMTP not configured. All emails use HTML templates in `app/templates/email/`. `enviar_email_marketing()` is the bulk-mail variant: multipart with a text/plain fallback plus `List-Unsubscribe`/`List-Unsubscribe-Post`/`Precedence` headers for deliverability.
- **`comunidade_service.py`** — Reddit-style community: `ComunidadePost`/`ComunidadeResposta` (flat, no reply nesting) with real upvote/downvote scoring via `ComunidadeVoto` (polymorphic `alvo_tipo`/`alvo_id`, one row per user+target, toggles/flips on repeat votes). `ComunidadeRelatorio` mirrors `RelatorioMaterial`'s report-queue pattern. The old sitewide ad banner (`Anuncio`/`_banner()`/`partials/banner.html`, unchanged) now only renders inside `comunidade/feed.html` as a "sponsored" card — `base.html`'s `{% block banner %}` is empty by default.
- **`marketing_service.py`** — sends `CampanhaEmail` (bulk marketing) campaigns in a background `threading.Thread` (no Celery/Redis). One `CampanhaEmailDestinatario` row per recipient makes sends resumable and idempotent. Throttled by `MARKETING_INTERVALO_SEGUNDOS` and capped by `MARKETING_LIMITE_DIARIO`/day; only targets `User.is_active and User.aceita_marketing`. Unsubscribe is handled by `main.cancelar_marketing` (public route, itsdangerous token, no expiry).
- **`creditos_service.py`** — thin wrappers around `User.ganhar_creditos()` / `User.gastar_creditos()`. Amounts come from app config keys (`CREDITOS_INICIAIS=10`, `CREDITOS_POR_UPLOAD_APROVADO=5`, `CREDITOS_POR_DOWNLOAD=1`).
- **`notificacoes_service.py`** — creates `Notificacao` rows; called from moderation approve/reject flows.

### Access control

Two decorators in `app/routes/admin.py`:
- `@admin_required` — `is_admin` only.
- `@moderador_required` — `is_admin OR is_moderador`.

Preview and download of **pending** materials: allowed for author, admin, or moderator. Approved materials: any logged-in user.

### Bulk import CLI

`manage.py importar-lote` expects the folder structure:
```
pasta/
  INSTITUICAO/
    DISCIPLINA/
      CATEGORIA/      ← must match an existing category name (fuzzy)
        file.pdf
```
Commits in batches of 100. Always run with `--dry-run` first.

### Templates

Base template: `app/templates/base.html`. Provides navbar, flash toasts, email confirmation banner, and footer. All pages extend it.

Error pages: `app/templates/errors/{404,403,429,500}.html`.
