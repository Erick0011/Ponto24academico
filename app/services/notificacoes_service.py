from app import db
from app.models.notificacao import Notificacao


def criar_notificacao(utilizador_id, tipo, titulo, mensagem=None, url=None):
    """Cria uma notificação in-app. O caller deve fazer db.session.commit()."""
    n = Notificacao(
        utilizador_id=utilizador_id,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        url=url,
    )
    db.session.add(n)
    return n


def notificar_aprovacao(material):
    """Notifica o autor de que o seu material foi aprovado."""
    from flask import url_for
    criar_notificacao(
        utilizador_id=material.autor_id,
        tipo=Notificacao.TIPO_MATERIAL_APROVADO,
        titulo=f"Material aprovado: {material.titulo_base}",
        mensagem="O teu material foi revisto e aprovado. Já está disponível na plataforma.",
        url=url_for("materiais.detalhe", id=material.id, _external=False),
    )


def notificar_rejeicao(material, motivo=None):
    """Notifica o autor de que o seu material foi rejeitado."""
    msg = "O teu material foi rejeitado."
    if motivo:
        msg += f" Motivo: {motivo}"
    criar_notificacao(
        utilizador_id=material.autor_id,
        tipo=Notificacao.TIPO_MATERIAL_REJEITADO,
        titulo=f"Material rejeitado: {material.titulo_base}",
        mensagem=msg,
    )
