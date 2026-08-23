import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    """Configuração base — partilhada por todos os ambientes."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-insegura")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies de sessão
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 50)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx"}

    # Créditos iniciais ao registar
    CREDITOS_INICIAIS = 10
    CREDITOS_POR_UPLOAD_APROVADO = 5
    CREDITOS_POR_DOWNLOAD = 1

    # Marketing / email em massa — limites de segurança para não sermos
    # marcados como spam ou bloqueados pelo servidor SMTP (ex: Gmail costuma
    # suspender contas que enviam rajadas de emails sem intervalo).
    MARKETING_INTERVALO_SEGUNDOS = int(os.environ.get("MARKETING_INTERVALO_SEGUNDOS", 3))
    MARKETING_LIMITE_DIARIO = int(os.environ.get("MARKETING_LIMITE_DIARIO", 300))


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'ponto24_dev.db')}"
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SESSION_COOKIE_SECURE = True

    # Em produção, exige SECRET_KEY segura
    @classmethod
    def init_app(cls, app):
        assert cls.SECRET_KEY != "dev-secret-key-insegura", \
            "Define SECRET_KEY no .env antes de usar em produção!"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
