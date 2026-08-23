from flask import current_app
from app import db
from app.models.user import User


def dar_creditos_upload(user: User):
    """Dá créditos ao utilizador quando o seu material é aprovado."""
    qtd = current_app.config.get("CREDITOS_POR_UPLOAD_APROVADO", 5)
    user.ganhar_creditos(qtd)
    user.total_uploads += 1
    db.session.commit()


def cobrar_creditos_download(user: User) -> bool:
    """
    Desconta créditos para download.
    Retorna True se sucesso, False se créditos insuficientes.
    """
    custo = current_app.config.get("CREDITOS_POR_DOWNLOAD", 1)
    if not user.tem_creditos(custo):
        return False
    user.gastar_creditos(custo)
    user.total_downloads += 1
    db.session.commit()
    return True


def creditos_ao_registar(user: User):
    """Atribui créditos iniciais quando o utilizador se regista."""
    qtd = current_app.config.get("CREDITOS_INICIAIS", 10)
    user.creditos = qtd
    db.session.commit()
