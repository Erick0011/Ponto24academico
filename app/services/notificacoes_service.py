import logging
from app import db
from app.models.notificacao import Notificacao

logger = logging.getLogger(__name__)


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


def notificar_moderadores_novo_material(material):
    """Notifica todos os admins/moderadores de que há um novo material pendente."""
    from flask import url_for
    from app.models.user import User
    from app.services.mail_service import email_novo_material_pendente

    moderadores = User.query.filter(
        db.or_(User.is_admin == True, User.is_moderador == True)
    ).all()

    url = url_for("admin.rever_material", id=material.id, _external=True)

    for mod in moderadores:
        criar_notificacao(
            utilizador_id=mod.id,
            tipo=Notificacao.TIPO_SISTEMA,
            titulo=f"Novo material para moderar: {material.titulo_base}",
            mensagem=f"Submetido por {material.autor.nome} — {material.instituicao}",
            url=url_for("admin.rever_material", id=material.id),
        )
        email_novo_material_pendente(material, mod, url)

    logger.info("Moderadores notificados: novo material #%s '%s'", material.id, material.titulo_base)


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
