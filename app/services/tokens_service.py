from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app

SALT_CONFIRMACAO = "confirmar-email"
SALT_RECUPERACAO = "recuperar-senha"
SALT_CONVITE     = "convite-acesso-antecipado"


def gerar_token(email: str, salt: str) -> str:
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps(email, salt=salt)


def verificar_token(token: str, salt: str, max_age: int = 3600):
    """Devolve o email se o token for válido, None caso contrário."""
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return s.loads(token, salt=salt, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
