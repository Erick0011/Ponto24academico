import os
from urllib.parse import urlencode
from flask import Flask, request as flask_request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


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

    # Context processor: injeta contagem de notificações não lidas em todos os templates
    from flask_login import current_user as _cu

    @app.context_processor
    def inject_notif_count():
        try:
            if _cu.is_authenticated:
                from app.models.notificacao import Notificacao as N
                count = N.query.filter_by(utilizador_id=_cu.id, lida=False).count()
                return {"notif_nao_lidas": count}
        except Exception:
            pass
        return {"notif_nao_lidas": 0}

    # Jinja2 global: constrói URL da página atual com `page` substituído
    @app.template_global()
    def paginate_url(page):
        args = flask_request.args.to_dict()
        args["page"] = str(page)
        return "?" + urlencode(args)

    # Handler de erros
    @app.errorhandler(403)
    def forbidden(e):
        return "Acesso negado.", 403

    @app.errorhandler(404)
    def not_found(e):
        return "Página não encontrada.", 404

    return app
