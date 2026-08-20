import os
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode
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
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
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

    # Endpoints acessíveis sem conta em modo pré-lançamento
    _ENDPOINTS_PUBLICOS_PRE = {
        "main.acesso_antecipado",
        "main.suporte",
        "auth.entrar",
        "auth.registar",
        "auth.confirmar_email",
        "auth.reenviar_confirmacao",
        "auth.email_nao_confirmado",
        "auth.recuperar_senha",
        "auth.redefinir_senha",
        "auth.sair",
        "static",
        "main.robots_txt",
        "main.sitemap_xml",
    }

    @app.before_request
    def bloquear_pre_lancamento():
        """Redireciona utilizadores não autenticados para a lista de espera quando activo."""
        if _cu.is_authenticated:
            return  # utilizadores com sessão passam sempre
        endpoint = flask_request.endpoint or ""
        if endpoint in _ENDPOINTS_PUBLICOS_PRE:
            return
        from app.models.configuracao import Configuracao as Cfg
        if Cfg.get("modo_pre_lancamento", "0") == "1":
            from flask import redirect, url_for
            return redirect(url_for("main.acesso_antecipado"))

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
            "modo_pre_lancamento": Cfg.get("modo_pre_lancamento", "0"),
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

    # Jinja2 global: constrói URL da página atual com `page` substituído
    @app.template_global()
    def paginate_url(page):
        args = flask_request.args.to_dict()
        args["page"] = str(page)
        return "?" + urlencode(args)

    # Cabeçalhos de segurança em toda a resposta
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
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
