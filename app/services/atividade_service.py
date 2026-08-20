import json
from sqlalchemy import func
from app import db
from app.models.atividade import AtividadeLog


def registar_atividade(evento, utilizador_id=None, alvo_tipo=None, alvo_id=None, detalhes=None):
    """Regista um evento de auditoria. O caller deve fazer db.session.commit().

    Nota: os serviços de créditos (app/services/creditos_service.py) fazem
    commit próprio — se um evento precisar de ser atómico com uma mudança de
    créditos, a chamada deve entrar dentro desse serviço, antes do seu commit.
    """
    if isinstance(detalhes, (dict, list)):
        detalhes = json.dumps(detalhes, ensure_ascii=False)
    log = AtividadeLog(
        evento=evento,
        utilizador_id=utilizador_id,
        alvo_tipo=alvo_tipo,
        alvo_id=alvo_id,
        detalhes=detalhes,
    )
    db.session.add(log)
    return log


def atividade_recente(limite=20):
    """Últimos eventos, mais recente primeiro — para o feed do KPI."""
    return (
        AtividadeLog.query
        .order_by(AtividadeLog.criado_em.desc())
        .limit(limite)
        .all()
    )


def contagem_por_evento(desde):
    """Contagem agrupada por tipo de evento desde uma data — para o KPI."""
    return (
        db.session.query(AtividadeLog.evento, func.count(AtividadeLog.id).label("n"))
        .filter(AtividadeLog.criado_em >= desde)
        .group_by(AtividadeLog.evento)
        .order_by(func.count(AtividadeLog.id).desc())
        .all()
    )
