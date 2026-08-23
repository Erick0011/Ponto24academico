import os
import json
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode, urlparse
from flask import Flask, request as flask_request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


class JsonFormatter(logging.Formatter):
    """Log aplicacional estruturado — uma linha JSON por evento (timestamp,
    nível, logger, mensagem, stack trace se houver). Nunca inclui passwords,
    tokens ou dados pessoais sensíveis: isso depende de quem chama o logger
    não os passar na mensagem, aqui não há sanitização automática de
    conteúdo livre. `admin/logs.html` (via admin.logs) sabe ler tanto este
    formato como o texto simples anterior, para não partir o histórico já
    gravado em disco antes desta mudança."""

    def format(self, record):
        dados = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            dados["exception"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)
csrf = CSRFProtect()
# Nota: armazenamento em memória — com `gunicorn -w 4` cada worker mantém o
# seu próprio contador, pelo que o limite real pode chegar a ~4x o definido.
# Aceitável para travar spam/abuso; para limites exatos, migrar para um
# storage partilhado (ex. Redis ou a mesma BD via RATELIMIT_STORAGE_URI).
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])


def create_app(config_name: str = None):
    """Application Factory — cria e configura a instância Flask."""

    app = Flask(__name__, instance_relative_config=False)

    # Configuração
    from config import config
    env = config_name or os.environ.get("FLASK_ENV", "development")
    config_class = config.get(env, config["default"])
    app.config.from_object(config_class)
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    if hasattr(config_class, "init_app"):
        config_class.init_app(app)

    # Garante que a pasta de uploads e logs existe
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    logs_dir = os.path.join(app.root_path, "..", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(logs_dir, "ponto24.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.INFO)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    logging.getLogger("app").addHandler(handler)
    logging.getLogger("app").setLevel(logging.INFO)

    # Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.entrar"
    login_manager.login_message = "Faz login para continuar."
    login_manager.login_message_category = "aviso"

    # Importar modelos para garantir que as tabelas são criadas
    from app.models.notificacao import Notificacao       # noqa: F401
    from app.models.configuracao import Configuracao     # noqa: F401
    from app.models.lista_espera import ListaEspera, RelatorioMaterial  # noqa: F401
    from app.models.anuncio import Anuncio               # noqa: F401
    from app.models.atividade import AtividadeLog         # noqa: F401
    from app.models.pasta import Pasta                    # noqa: F401
    from app.models.campanha_email import CampanhaEmail, CampanhaEmailDestinatario  # noqa: F401
    from app.models.visita import VisitaLog                # noqa: F401

    # User loader para Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.materiais import materiais_bp
    from app.routes.admin import admin_bp
    from app.routes.notificacoes import notificacoes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(materiais_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notificacoes_bp)

    # Bloqueio de conta após 7 dias sem confirmação de email
    from flask_login import current_user as _cu
    from datetime import datetime, timedelta

    PRAZO_CONFIRMACAO = 7  # dias

    @app.before_request
    def verificar_email_confirmado():
        if not _cu.is_authenticated:
            return
        if _cu.email_verificado:
            return
        # Endpoints sempre permitidos (confirmação, logout, static)
        endpoint = flask_request.endpoint or ""
        permitidos = {"auth.confirmar_email", "auth.reenviar_confirmacao",
                      "auth.sair", "auth.email_nao_confirmado", "static"}
        if endpoint in permitidos:
            return
        # Verifica se já passaram 7 dias
        limite = _cu.criado_em + timedelta(days=PRAZO_CONFIRMACAO)
        if datetime.utcnow() > limite:
            from flask import redirect, url_for
            return redirect(url_for("auth.email_nao_confirmado"))

    # Context processor: injeta contagem de notificações, dias restantes e config pública
    @app.context_processor
    def inject_notif_count():
        from app.models.configuracao import Configuracao as Cfg
        cfg = {
            "email_suporte": Cfg.get("email_suporte", "suporte@ponto24academico.com"),
            "whatsapp":      Cfg.get("whatsapp", ""),
            "instagram":     Cfg.get("instagram", ""),
        }
        try:
            if _cu.is_authenticated:
                from app.models.notificacao import Notificacao as N
                count = N.query.filter_by(utilizador_id=_cu.id, lida=False).count()
                dias_restantes = None
                if not _cu.email_verificado:
                    limite = _cu.criado_em + timedelta(days=PRAZO_CONFIRMACAO)
                    dias_restantes = max(0, (limite - datetime.utcnow()).days)
                return {"notif_nao_lidas": count, "dias_confirmacao": dias_restantes, "cfg": cfg, "thumb_url": _thumb_url, "banner_ativo": _banner()}
        except Exception:
            pass
        return {"notif_nao_lidas": 0, "dias_confirmacao": None, "cfg": cfg, "thumb_url": _thumb_url, "banner_ativo": _banner()}

    # Selecciona banner activo e resolve URL da imagem
    def _banner():
        try:
            from app.models.anuncio import Anuncio
            b = Anuncio.selecionar()
            if b and b.banner_key:
                if os.environ.get("R2_ENDPOINT"):
                    from app.services.r2_service import presigned_url
                    b.banner_url = presigned_url(b.banner_key, expires=3600)
                else:
                    b.banner_url = "/static/anuncios/" + b.banner_key.split("/")[-1]
            return b
        except Exception:
            return None

    # Função auxiliar para URL de thumbnail (local ou R2)
    def _thumb_url(material):
        if not getattr(material, "e_imagem", False) or not material.ficheiro_path:
            return None
        from pathlib import Path
        p = Path(material.ficheiro_path.replace("\\", "/"))
        if os.environ.get("R2_ENDPOINT"):
            from app.services.r2_service import presigned_url
            thumb_key = f"{p.parent.as_posix()}/thumbs/{p.name}"
            return presigned_url(thumb_key, expires=7200)
        return flask_request.url_root.rstrip("/") + "/static/uploads/" + p.parent.as_posix() + "/thumbs/" + p.name

    # Jinja2 filtro: "há 3 horas" em vez de "22/08/2026 14:07".
    #
    # Todas as datas do modelo são gravadas com datetime.utcnow(), por isso a
    # comparação é feita também em UTC.
    @app.template_filter("tempo_relativo")
    def tempo_relativo(quando):
        from datetime import datetime as _dt
        if not quando:
            return ""
        segundos = (_dt.utcnow() - quando).total_seconds()

        # Relógios ligeiramente adiantados dariam "há -4 segundos".
        if segundos < 60:
            return "agora mesmo"
        minutos = segundos / 60
        if minutos < 60:
            n = int(minutos)
            return f"há {n} minuto{'s' if n != 1 else ''}"
        horas = minutos / 60
        if horas < 24:
            n = int(horas)
            return f"há {n} hora{'s' if n != 1 else ''}"
        dias = horas / 24
        if dias < 7:
            n = int(dias)
            return f"há {n} dia{'s' if n != 1 else ''}"
        if dias < 30:
            n = int(dias / 7)
            return f"há {n} semana{'s' if n != 1 else ''}"
        if dias < 365:
            n = int(dias / 30)
            return f"há {n} {'meses' if n != 1 else 'mês'}"
        # A partir de um ano a data exata volta a ser mais informativa.
        return quando.strftime("%d/%m/%Y")

    # Jinja2 global: constrói URL da página atual com `page` substituído
    @app.template_global()
    def paginate_url(page):
        args = flask_request.args.to_dict()
        args["page"] = str(page)
        return "?" + urlencode(args)

    # ── Estatísticas de tráfego (todos os visitantes, mesmo sem conta) ───────────
    # Cookie técnico anónimo — só um identificador aleatório, sem dados pessoais —
    # para contar visitas/visitantes únicos. Ver privacidade.html, secção "Cookies".
    COOKIE_VISITANTE = "p24_vid"
    PREFIXOS_IGNORADOS_TRACKING = ("admin.", "static")  # tráfego interno/estático não conta

    @app.before_request
    def registar_visita():
        from flask import g
        endpoint = flask_request.endpoint
        if not endpoint or flask_request.method != "GET":
            return
        if endpoint.startswith(PREFIXOS_IGNORADOS_TRACKING):
            return

        sessao_id = flask_request.cookies.get(COOKIE_VISITANTE)
        g.visita_sessao_nova = sessao_id is None
        if sessao_id is None:
            from app.models.visita import novo_sessao_id
            sessao_id = novo_sessao_id()
        g.visita_sessao_id = sessao_id

        try:
            from app.models.visita import VisitaLog
            db.session.add(VisitaLog(
                sessao_id=sessao_id,
                utilizador_id=_cu.id if _cu.is_authenticated else None,
                caminho=flask_request.path[:255],
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # frame-src da CSP: a pré-visualização de PDFs (materials/detalhe.html) usa
    # um <iframe> para /materiais/<id>/preview. Em local/dev isso é sempre a
    # própria origem ('self'), mas em produção com R2 configurado essa rota
    # faz *redirect* para um URL assinado no domínio do R2 (origem diferente)
    # — sem isto no frame-src, a CSP cai no default-src 'self' e bloqueia o
    # iframe em silêncio (só visível na consola do browser).
    _csp_frame_src = "'self'"
    _r2_endpoint = os.environ.get("R2_ENDPOINT")
    if _r2_endpoint:
        _r2_host = urlparse(_r2_endpoint).netloc
        if _r2_host:
            _csp_frame_src += f" https://{_r2_host}"
            _r2_dominio_pai = _r2_host.split(".", 1)[-1]
            if _r2_dominio_pai != _r2_host:
                # cobre também o endereçamento virtual-hosted (bucket.<host>)
                _csp_frame_src += f" https://*.{_r2_dominio_pai}"

    # Rotas que devolvem o ficheiro cru (PDF, imagem, docx) em vez de HTML.
    # A CSP da aplicação NÃO pode ser aplicada a estas respostas: quando um PDF
    # é servido com "default-src 'self'", o object-src herda 'self' e o Chrome
    # recusa-se a instanciar o seu visualizador interno de PDF (que vive numa
    # origem chrome-extension://) — o resultado é um painel completamente
    # branco, sem erro visível. Era esta a causa de "os PDFs não abrem".
    _ENDPOINTS_FICHEIRO_CRU = {"materiais.preview", "materiais.download"}

    # Cabeçalhos de segurança em toda a resposta
    @app.after_request
    def set_security_headers(response):
        from flask import g
        if getattr(g, "visita_sessao_nova", False):
            response.set_cookie(
                COOKIE_VISITANTE, g.visita_sessao_id,
                max_age=365 * 24 * 3600, httponly=True, samesite="Lax",
                secure=not app.debug,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        # SAMEORIGIN (não DENY): a pré-visualização de materiais usa um <iframe>
        # para PDFs (materials/detalhe.html), que o DENY bloqueava mesmo sendo
        # a própria origem a carregar-se a si mesma.
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if flask_request.endpoint in _ENDPOINTS_FICHEIRO_CRU:
            # Sem CSP: o "nosniff" acima já garante que o ficheiro nunca é
            # interpretado como HTML, por isso não há aqui superfície de XSS
            # para a CSP proteger — só o visualizador de PDF a perder.
            response.headers.pop("Content-Security-Policy", None)
        else:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "img-src 'self' data: blob: https:; "
                f"frame-src {_csp_frame_src}; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                # O pdf.js corre a descodificação num Web Worker e, em alguns
                # browsers, arranca-o a partir de um blob: URL.
                "worker-src 'self' blob:; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:;"
            )
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Handlers de erros
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app
