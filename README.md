# Ponto 24 Académico

**A maior plataforma digital de materiais académicos para estudantes angolanos.**

---

## O problema

Todos os anos, milhares de provas, resumos e exercícios circulam entre estudantes angolanos —
mas dispersos em grupos de WhatsApp, perdidos em chats antigos, sem contexto e sem forma de
saber se valem a pena antes de abrir o ficheiro. Quem não tem os contactos certos simplesmente
fica de fora. E quem contribui, contribui de graça, sem nada em troca.

## O que é o Ponto 24

O **Ponto 24 Académico** junta tudo isso num único lugar, organizado por instituição, curso,
disciplina e ano — com pesquisa, pré-visualização antes de descarregar, e avaliações de quem já
usou o material. Ninguém precisa de "conhecer alguém" para ter acesso a boas provas e resumos.

Funciona com um sistema de **créditos**: ganha-se ao partilhar materiais aprovados, gasta-se ao
descarregar. Quem dá, recebe primeiro — e a plataforma cresce com quem a usa, não apesar de quem
a usa.

Não é uma plataforma genérica traduzida para Angola — é feita a pensar em como os estudantes
angolanos já partilham (WhatsApp, grupos, boca-a-boca) e no que lhes falta: organização, acesso
justo e reconhecimento por quem contribui.

**Website:** [ponto24academico.com](https://ponto24academico.com)

---

Este README tem duas partes: esta primeira, para quem quer perceber **o que é o projeto**; e a
segunda, mais abaixo, para quem quer **correr o código**. Se és programador e só queres pôr isto
a correr localmente, salta para a [instalação local](#instalação-local).

---

## Índice

- [O problema](#o-problema)
- [O que é o Ponto 24](#o-que-é-o-ponto-24)
- [Funcionalidades](#funcionalidades)
- [Stack tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Instalação local](#instalação-local)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Comandos úteis](#comandos-úteis-manage-py)
- [Deployment em produção](#deployment-em-produção)
- [Documentação técnica](#documentação-técnica)
- [Segurança](#segurança)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## Funcionalidades

**Materiais académicos**
- Submissão de ficheiros (PDF, DOCX, imagens) com deteção de duplicados por hash SHA-256
- Fila de moderação (aprovar/rejeitar) antes de um material ficar público
- Pesquisa e filtros por instituição, curso, disciplina, ano letivo e categoria
- Sistema de pastas hierárquico (profundidade livre) para curadoria — os ficheiros são fisicamente reorganizados no armazenamento para espelhar a árvore
- Avaliações (1-5 estrelas), favoritos e contagem de visualizações/downloads
- Denúncia de conteúdo inadequado

**Gamificação**
- Créditos ganhos ao registar e ao publicar materiais aprovados
- Créditos gastos ao fazer download
- Níveis (Novato → Expert) derivados do saldo de créditos

**Conta e comunicação**
- Registo/login com confirmação de email obrigatória (prazo de 7 dias)
- Recuperação de palavra-passe por token com expiração
- Notificações in-app
- Emails transacionais (boas-vindas, aprovação/rejeição de material, candidaturas, etc.)
- Secção de Marketing: campanhas de email em massa com throttle, limite diário e cancelamento de subscrição — pensada para não bloquear a conta de envio

**Administração**
- Painel com KPIs e log de auditoria de todas as ações relevantes
- Gestão de utilizadores (promover admin/moderador, ativar/desativar, ajustar créditos)
- Gestão de categorias, pastas, anúncios (banners patrocinados) e configurações gerais
- Fila de candidaturas para colaboradores/voluntários, com email automático de resposta
- Lista de espera / acesso antecipado (modo pré-lançamento opcional)
- Importação em massa de materiais via CLI

**Segurança**
- Honeypot + rate limiting (Flask-Limiter) em todos os formulários públicos, sem CAPTCHA de terceiros
- Cabeçalhos de segurança (CSP, X-Frame-Options, HSTS, etc.)
- Política de palavra-passe forte, cookies de sessão seguros

---

## Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.10+, Flask 3 (padrão *application factory* + Blueprints) |
| Base de dados | SQLAlchemy + Flask-Migrate (Alembic); SQLite em desenvolvimento, PostgreSQL em produção |
| Autenticação | Flask-Login, `werkzeug.security` para hashing de senhas |
| Formulários/CSRF | Flask-WTF |
| Rate limiting | Flask-Limiter |
| Armazenamento de ficheiros | Disco local (padrão) ou Cloudflare R2 (S3-compatible, via `boto3`) |
| Email | SMTP puro (`smtplib`), sem Flask-Mail |
| Imagens | Pillow (geração de thumbnails) |
| Frontend | Bootstrap 5.3 + Bootstrap Icons (CDN), CSS próprio (`ponto24.css`), JavaScript vanilla |
| Produção | Gunicorn |

Sem frontend framework (React/Vue) — server-side rendering com Jinja2.

---

## Arquitetura

A app segue o padrão **application factory**: `create_app()` em `app/__init__.py` monta a aplicação, regista extensões, blueprints e hooks. Cinco blueprints organizam as rotas por área:

| Blueprint | Prefixo | Ficheiro |
|---|---|---|
| `auth` | `/auth` | `app/routes/auth.py` |
| `main` | `/` | `app/routes/main.py` |
| `materiais` | `/materiais` | `app/routes/materiais.py` |
| `admin` | `/admin` | `app/routes/admin.py` |
| `notificacoes` | `/notificacoes` | `app/routes/notificacoes.py` |

A lógica de negócio fica em `app/services/` (upload, email, créditos, notificações, tokens, campanhas de marketing) — as rotas ficam finas, delegando a estes serviços. Os modelos SQLAlchemy vivem em `app/models/`, um ficheiro por domínio.

Para uma explicação detalhada de cada ficheiro, ver a [documentação técnica](#documentação-técnica).

---

## Estrutura do projeto

```
Ponto24academico/
├── app/
│   ├── __init__.py            # Application factory, extensões, hooks, context processors
│   ├── models/                # Um ficheiro por domínio (User, Material, Pasta, ...)
│   ├── routes/                # Blueprints: auth, main, materiais, admin, notificacoes
│   ├── services/               # Lógica de negócio (upload, email, créditos, marketing, ...)
│   ├── utils/                  # Helpers (honeypot, validação de senha)
│   ├── static/
│   │   ├── css/ponto24.css     # Design system próprio
│   │   ├── img/
│   │   └── uploads/            # Ficheiros enviados (só em armazenamento local)
│   └── templates/               # Jinja2, organizado por área (admin/, materials/, email/, ...)
├── config/
│   └── settings.py             # Config por ambiente (Development/Production/Testing)
├── migrations/                  # Migrações Alembic (Flask-Migrate)
├── docs/
│   ├── TESTES.md                # Checklist manual de testes (200+ itens)
│   └── PONTO24_DOCUMENTACAO_TECNICA.pdf  # Documentação técnica completa
├── manage.py                    # Comandos CLI (seed-db, criar-admin, importar-lote, ...)
├── run.py                       # Ponto de entrada em desenvolvimento
├── wsgi.py                      # Ponto de entrada para Gunicorn
├── requirements.txt
└── .env.example
```

---

## Instalação local

Requisitos: Python 3.10+, pip, git.

```bash
# 1. Clonar
git clone https://github.com/Erick0011/Ponto24academico.git
cd Ponto24academico

# 2. Ambiente virtual
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Dependências
pip install -r requirements.txt

# 4. Variáveis de ambiente
cp .env.example .env
# edita o .env — define pelo menos SECRET_KEY com um valor aleatório seguro:
python -c "import secrets; print(secrets.token_hex(24))"

# 5. Base de dados
flask --app manage.py db upgrade
flask --app manage.py seed-db

# 6. Utilizador administrador
# a senha tem de ter 8+ caracteres, maiúscula, minúscula e número
flask --app manage.py criar-admin admin@exemplo.com SenhaForte123

# 7. Arrancar
python run.py
```

Acede em **http://localhost:5000**. Sem `R2_ENDPOINT` definido no `.env`, os ficheiros são guardados em disco local (`app/static/uploads/`) — suficiente para testar tudo localmente.

---

## Variáveis de ambiente

Ver `.env.example` para a lista completa e comentada. As mais relevantes:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | Sim | Chave de assinatura de sessões/tokens — nunca usar o valor de exemplo em produção |
| `DATABASE_URL` | Não | `sqlite:///...` por defeito; `postgresql://...` em produção |
| `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | Não | Sem isto, o envio de email é ignorado silenciosamente (útil em dev) |
| `MARKETING_INTERVALO_SEGUNDOS`, `MARKETING_LIMITE_DIARIO` | Não | Throttle de campanhas de email em massa (padrão: 3s, 300/dia) |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Não | Se definidos, os ficheiros vão para Cloudflare R2 em vez de disco local |
| `MAX_CONTENT_LENGTH_MB` | Não | Limite de tamanho de upload (padrão: 50 MB) |

---

## Comandos úteis (`manage.py`)

```bash
flask --app manage.py seed-db                              # cria as categorias base
flask --app manage.py criar-admin <email> <password>       # cria/promove um admin
flask --app manage.py testar-email <destinatario>           # envia emails de teste
flask --app manage.py importar-lote ./pasta --dry-run       # pré-visualiza importação em massa
flask --app manage.py importar-lote ./pasta --auto-aprovar --ano-letivo "2024/2025"

flask --app manage.py db migrate -m "descrição"             # gera nova migração
flask --app manage.py db upgrade                            # aplica migrações
```

---

## Deployment em produção

```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

Checklist mínimo:
- `FLASK_ENV=production` e uma `SECRET_KEY` forte (a app recusa arrancar em produção com a chave de exemplo)
- `DATABASE_URL` a apontar para PostgreSQL
- `SESSION_COOKIE_SECURE` fica automaticamente ativo em produção (exige HTTPS)
- Configurar `R2_*` para armazenamento persistente de ficheiros (discos locais não sobrevivem a deploys em muitas plataformas)
- Configurar `MAIL_*` para envio real de email

---

## Documentação técnica

- **`docs/TESTES.md`** — checklist manual de testes funcionais, organizado por fase de desenvolvimento (200+ itens).
- **`docs/PONTO24_DOCUMENTACAO_TECNICA.pdf`** — documentação técnica completa, pasta a pasta e ficheiro a ficheiro: o que cada módulo faz, principais funções/classes, decisões de arquitetura (caminho materializado nas pastas, convenção "add mas não commit" nos serviços, mover ficheiros com garantia all-or-nothing, etc.) — pensada para debugging e para planear melhorias futuras.

---

## Segurança

- Formulários públicos protegidos por honeypot + rate limiting (Flask-Limiter) — sem CAPTCHA de terceiros
- Palavra-passe obrigatoriamente forte (8+ caracteres, maiúscula, minúscula, dígito)
- Cookies de sessão `HttpOnly` + `SameSite=Lax` (`Secure` em produção)
- Cabeçalhos de segurança em todas as respostas: CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS
- Emails de marketing incluem cabeçalhos `List-Unsubscribe`/`List-Unsubscribe-Post` (RFC 8058) e respeitam um limite diário de envio, para reduzir o risco de o remetente ser bloqueado

Encontraste uma vulnerabilidade? Contacta a equipa através da página de Suporte em vez de abrir uma issue pública.

---

## Roadmap

- [x] Segurança, painel admin profissional, candidaturas, log de auditoria
- [x] Sistema de pastas hierárquico com reorganização física dos ficheiros
- [x] Email automático de candidaturas + campanhas de marketing em massa
- [ ] API REST (para uma futura app mobile)
- [ ] Testes automatizados (atualmente o checklist em `docs/TESTES.md` é manual)

---

## Licença

A definir pelo mantenedor do projeto.
