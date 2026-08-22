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


def _auditar_creditos_comunidade(user: User, acao: str, qtd: int):
    """As 3 funções abaixo mutam User.creditos, que o listener automático de
    comunidade_auditoria_service não vigia (User não é um model "da
    Comunidade" — auditar todos os seus campos seria demasiado amplo).
    Aqui a atribuição É especificamente de créditos da Comunidade, por isso
    regista-se explicitamente."""
    from app.services.comunidade_auditoria_service import registar_auditoria_evento
    registar_auditoria_evento(
        action=acao, entity_type="user_creditos", entity_id=user.id,
        payload_after={"creditos_ganhos": qtd, "saldo_final": user.creditos},
    )


def dar_creditos_comunidade_post(user: User):
    """Dá créditos ao publicar um post na Comunidade."""
    qtd = current_app.config.get("CREDITOS_POR_POST_COMUNIDADE", 2)
    user.ganhar_creditos(qtd)
    _auditar_creditos_comunidade(user, "creditos_post_comunidade", qtd)
    db.session.commit()


def dar_creditos_comunidade_resposta(user: User):
    """Dá créditos ao responder a um post na Comunidade."""
    qtd = current_app.config.get("CREDITOS_POR_RESPOSTA_COMUNIDADE", 1)
    user.ganhar_creditos(qtd)
    _auditar_creditos_comunidade(user, "creditos_resposta_comunidade", qtd)
    db.session.commit()


def dar_creditos_melhor_resposta(user: User):
    """Dá créditos a quem tem a resposta marcada como melhor resposta pelo
    autor do tópico (ou por um moderador)."""
    qtd = current_app.config.get("CREDITOS_POR_MELHOR_RESPOSTA", 5)
    user.ganhar_creditos(qtd)
    _auditar_creditos_comunidade(user, "creditos_melhor_resposta", qtd)
    db.session.commit()
