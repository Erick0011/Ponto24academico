"""Log de auditoria imutável da Comunidade (comunidade_audit_log).

Em vez de espalhar chamadas manuais por cada rota (criar/editar/eliminar
post, resposta, categoria, denúncia, ...), um único listener SQLAlchemy
(`session.before_flush`, registado uma vez em `init_app`) apanha todas as
mutações dos modelos auditados automaticamente — é o "helper único ou event
listeners SQLAlchemy" pedido. Ações que não mudam um destes modelos
diretamente (moderação, mudança de papel, atribuição de créditos, publicação
de anúncio) continuam a chamar `registar_auditoria_evento` explicitamente,
porque não há um "antes/depois" de linha de BD óbvio para capturar sozinho.

Regra de imutabilidade: nada nesta base de código deve alguma vez fazer
UPDATE ou DELETE sobre ComunidadeAuditLog — só o INSERT feito aqui.

Limitação conhecida: numa criação, o `entity_id` fica None neste log — o id
só é atribuído pela BD durante o próprio flush que estamos a interceptar.
O payload_after guarda os restantes campos (título, autor, etc.), suficiente
para identificar o registo por proximidade temporal; length não vale a pena
a complexidade extra de um segundo flush só para preencher isto."""

from sqlalchemy import event, inspect as sa_inspect
from flask import request, has_request_context
from flask_login import current_user
from app.models.comunidade import (
    ComunidadePost, ComunidadeResposta, ComunidadeCategoria, ComunidadeRelatorio,
    ComunidadeAuditLog,
)

_MODELOS_AUDITADOS = {
    ComunidadePost: "comunidade_post",
    ComunidadeResposta: "comunidade_resposta",
    ComunidadeCategoria: "comunidade_categoria",
    ComunidadeRelatorio: "comunidade_relatorio",
}


def _serializar(valores: dict):
    limpo = {}
    for chave, valor in valores.items():
        limpo[chave] = valor if isinstance(valor, (str, int, float, bool, type(None))) else str(valor)
    return limpo


def _snapshot(obj) -> dict:
    insp = sa_inspect(obj)
    return _serializar({attr.key: getattr(obj, attr.key, None) for attr in insp.mapper.column_attrs})


def _ip_e_user_agent():
    if not has_request_context():
        return None, None
    ip = request.remote_addr[:64] if request.remote_addr else None
    ua = (request.user_agent.string or "")[:300] if request.user_agent else None
    return ip, ua


def _ator_id():
    try:
        return current_user.id if current_user.is_authenticated else None
    except Exception:
        return None  # fora de contexto de request/sessão (ex: script de manutenção)


def registar_auditoria_evento(action: str, entity_type: str, entity_id: int = None,
                               payload_before: dict = None, payload_after: dict = None):
    """Para ações sem uma linha de BD única para o listener capturar sozinho
    (moderação, mudança de papel, atribuição de créditos, publicação de
    anúncio, criação/remoção de ligação). O caller ainda faz o commit."""
    from app import db
    ip, ua = _ip_e_user_agent()
    log = ComunidadeAuditLog(
        actor_user_id=_ator_id(), action=action, entity_type=entity_type, entity_id=entity_id,
        payload_before=_serializar(payload_before) if payload_before else None,
        payload_after=_serializar(payload_after) if payload_after else None,
        ip=ip, user_agent=ua,
    )
    db.session.add(log)
    return log


def _on_before_flush(session, flush_context, instances):
    ip, ua = _ip_e_user_agent()
    ator_id = _ator_id()

    for obj in list(session.new):
        entity_type = _MODELOS_AUDITADOS.get(type(obj))
        if not entity_type:
            continue
        session.add(ComunidadeAuditLog(
            actor_user_id=ator_id, action="criado", entity_type=entity_type, entity_id=None,
            payload_after=_snapshot(obj), ip=ip, user_agent=ua,
        ))

    for obj in list(session.dirty):
        entity_type = _MODELOS_AUDITADOS.get(type(obj))
        if not entity_type or not session.is_modified(obj, include_collections=False):
            continue
        insp = sa_inspect(obj)
        antes = {}
        houve_mudanca = False
        for attr in insp.mapper.column_attrs:
            hist = insp.get_history(attr.key, True)
            if hist.has_changes():
                houve_mudanca = True
                antes[attr.key] = hist.deleted[0] if hist.deleted else None
        if not houve_mudanca:
            continue
        session.add(ComunidadeAuditLog(
            actor_user_id=ator_id, action="editado", entity_type=entity_type, entity_id=obj.id,
            payload_before=_serializar(antes), payload_after=_snapshot(obj), ip=ip, user_agent=ua,
        ))

    for obj in list(session.deleted):
        entity_type = _MODELOS_AUDITADOS.get(type(obj))
        if not entity_type:
            continue
        session.add(ComunidadeAuditLog(
            actor_user_id=ator_id, action="eliminado", entity_type=entity_type, entity_id=obj.id,
            payload_before=_snapshot(obj), ip=ip, user_agent=ua,
        ))


def init_app(app):
    """Regista o listener uma única vez (chamado em create_app)."""
    from app import db
    event.listen(db.session, "before_flush", _on_before_flush)
