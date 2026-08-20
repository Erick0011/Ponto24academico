"""Lógica partilhada da Comunidade — votação (post e resposta usam a mesma
tabela ComunidadeVoto, com alvo_tipo/alvo_id) e construção da query do feed."""

from app import db
from app.models.comunidade import ComunidadePost, ComunidadeVoto


def aplicar_voto(utilizador, alvo_tipo: str, alvo_id: int, alvo_obj, valor: int) -> int:
    """Aplica um voto (+1 ou -1) de um utilizador a um post/resposta.

    Clicar de novo no mesmo valor remove o voto (toggle off); clicar no
    valor oposto troca-o. Atualiza alvo_obj.votos_score de imediato e
    devolve o delta aplicado. O caller ainda tem de fazer db.session.commit().
    """
    existente = ComunidadeVoto.query.filter_by(
        utilizador_id=utilizador.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id
    ).first()

    if existente is None:
        db.session.add(ComunidadeVoto(
            utilizador_id=utilizador.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id, valor=valor,
        ))
        delta = valor
    elif existente.valor == valor:
        db.session.delete(existente)
        delta = -valor
    else:
        delta = valor - existente.valor
        existente.valor = valor

    alvo_obj.votos_score += delta
    return delta


def voto_do_utilizador(utilizador, alvo_tipo: str, alvo_id: int):
    """Devolve o valor do voto atual do utilizador (+1/-1) ou None."""
    if not utilizador or not utilizador.is_authenticated:
        return None
    v = ComunidadeVoto.query.filter_by(
        utilizador_id=utilizador.id, alvo_tipo=alvo_tipo, alvo_id=alvo_id
    ).first()
    return v.valor if v else None


def feed_query(tipo: str = None, ordenar: str = "recentes"):
    """Query base do feed da Comunidade: posts fixados primeiro, depois
    ordenados por data ou por pontuação de votos."""
    query = ComunidadePost.query
    if tipo:
        query = query.filter_by(tipo=tipo)

    if ordenar == "votados":
        query = query.order_by(ComunidadePost.fixado.desc(), ComunidadePost.votos_score.desc(),
                                ComunidadePost.criado_em.desc())
    else:
        query = query.order_by(ComunidadePost.fixado.desc(), ComunidadePost.criado_em.desc())

    return query
