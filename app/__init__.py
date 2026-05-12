import os
from urllib.parse import urlencode
from flask import Flask, request as flask_request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name: str = None):
    """Application Factory — cria e configura a instância Flask."""

    app = Flask(__name__, instance_relative_config=False)

    # Configuração
    from config import config
    env = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config.get(env, config["default"]))

    # Garante que a pasta de uploads existe
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Extensões
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.entrar"
    login_manager.login_message = "Faz login para continuar."
    login_manager.login_message_category = "aviso"

    # Importar modelos para garantir que as tabelas são criadas
    from app.models.notificacao import Notificacao  # noqa: F401

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

    # Context processor: injeta contagem de notificações e dias restantes
    @app.context_processor
    def inject_notif_count():
        try:
            if _cu.is_authenticated:
                from app.models.notificacao import Notificacao as N
                count = N.query.filter_by(utilizador_id=_cu.id, lida=False).count()
                dias_restantes = None
                if not _cu.email_verificado:
                    limite = _cu.criado_em + timedelta(days=PRAZO_CONFIRMACAO)
                    dias_restantes = max(0, (limite - datetime.utcnow()).days)
                return {"notif_nao_lidas": count, "dias_confirmacao": dias_restantes}
        except Exception:
            pass
        return {"notif_nao_lidas": 0, "dias_confirmacao": None}

    # Jinja2 global: constrói URL da página atual com `page` substituído
    @app.template_global()
    def paginate_url(page):
        args = flask_request.args.to_dict()
        args["page"] = str(page)
        return "?" + urlencode(args)

    # Handlers de erros
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app
