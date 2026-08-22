"""Reações nomeadas (Útil / Obrigado / Resolvido) da Comunidade — a par do
voto genérico (+1/-1) já existente em comunidade_service.py, não em
substituição. Mesmo padrão alvo_tipo/alvo_id."""

from collections import defaultdict
from app import db
from app.models.comunidade import ComunidadeReacao


def alternar_reacao(utilizador, alvo_tipo: str, alvo_id: int, tipo: str) -> bool:
    """Liga/desliga uma reação. Devolve True se ficou ligada, False se foi
    removida. O caller ainda tem de fazer db.session.commit()."""
    existente = ComunidadeReacao.query.filter_by(
        utilizador_id=utilizador.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id, tipo=tipo
    ).first()
    if existente:
        db.session.delete(existente)
        return False
    db.session.add(ComunidadeReacao(
        utilizador_id=utilizador.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id, tipo=tipo,
    ))
    return True


def reacoes_de(alvo_tipo: str, alvo_ids: list, utilizador=None):
    """Devolve (contagens, minhas):
      contagens = {alvo_id: {tipo: n}}
      minhas    = {alvo_id: set(tipos que `utilizador` marcou)} — vazio se
                  não autenticado.
    Uma única query para todos os `alvo_ids` pedidos (evita N+1 numa página
    com várias respostas)."""
    contagens = defaultdict(lambda: defaultdict(int))
    minhas = defaultdict(set)
    if not alvo_ids:
        return contagens, minhas

    todas = ComunidadeReacao.query.filter(
        ComunidadeReacao.alvo_tipo == alvo_tipo,
        ComunidadeReacao.alvo_id.in_(alvo_ids),
    ).all()
    for r in todas:
        contagens[r.alvo_id][r.tipo] += 1
        if utilizador is not None and getattr(utilizador, "is_authenticated", False) and r.utilizador_id == utilizador.id:
            minhas[r.alvo_id].add(r.tipo)
    return contagens, minhas
