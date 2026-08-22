"""Lógica partilhada da Comunidade — votação (post e resposta usam a mesma
tabela ComunidadeVoto, com alvo_tipo/alvo_id) e construção da query do feed."""

from datetime import datetime
from app import db
from app.models.comunidade import ComunidadePost, ComunidadeVoto, ComunidadeTag, ComunidadeCategoria
from app.services.pesquisa_service import condicoes_e_pontuacao


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


def feed_query(tipo: str = None, categoria: str = None, tag: str = None, busca: str = None, ordenar: str = "recentes"):
    """Query base do feed da Comunidade: posts fixados (e ainda dentro do
    prazo) primeiro, depois ordenados por relevância (havendo pesquisa),
    pontuação de votos ou data.

    `categoria` (slug) é o filtro atual, mostrado na UI. `tipo` fica só para
    não partir links antigos que ainda apontem para o enum legado — os dois
    podem ser combinados (AND) se algum dia vierem juntos num link."""
    query = ComunidadePost.query
    if tipo:
        query = query.filter_by(tipo=tipo)
    if categoria:
        query = query.join(ComunidadePost.categoria).filter(ComunidadeCategoria.slug == categoria)
    if tag:
        query = query.join(ComunidadePost.tags).filter(ComunidadeTag.slug == tag)

    relevancia = None
    if busca:
        condicao, relevancia = condicoes_e_pontuacao(busca, [
            (ComunidadePost.titulo, 5), (ComunidadePost.corpo, 1),
        ])
        if condicao is not None:
            query = query.filter(condicao)

    # Só conta como "fixado" para efeitos de ordenação se ainda estiver dentro
    # do prazo — espelha ComunidadePost.esta_fixado_ativo em SQL puro, porque
    # não dá para ordenar por uma property Python.
    fixado_ativo = db.case(
        (db.and_(ComunidadePost.fixado.is_(True),
                 db.or_(ComunidadePost.fixado_ate.is_(None),
                        ComunidadePost.fixado_ate > datetime.utcnow())), 0),
        else_=1,
    )

    desempate = (
        [ComunidadePost.votos_score.desc(), ComunidadePost.criado_em.desc()]
        if ordenar == "votados" else
        [ComunidadePost.criado_em.desc()]
    )
    if relevancia is not None:
        query = query.order_by(fixado_ativo, relevancia.desc(), *desempate)
    else:
        query = query.order_by(fixado_ativo, *desempate)

    return query


def anuncios_fixados_ativos(limite: int = 3):
    """Anúncios oficiais (categoria apenas_admin) atualmente fixados e dentro
    do prazo — para o banner no topo da Comunidade e, opcionalmente, na
    página inicial do site."""
    return (
        ComunidadePost.query
        .join(ComunidadePost.categoria)
        .filter(
            ComunidadeCategoria.apenas_admin.is_(True),
            ComunidadePost.fixado.is_(True),
            db.or_(ComunidadePost.fixado_ate.is_(None), ComunidadePost.fixado_ate > datetime.utcnow()),
        )
        .order_by(ComunidadePost.criado_em.desc())
        .limit(limite)
        .all()
    )
