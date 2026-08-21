"""Recomendação de conteúdo — baseada em regras, não em histórico de
navegação: usa dados que já existem (disciplina/instituição/curso do perfil,
categoria/disciplina/instituição do material, tags/tipo dos posts em que o
próprio utilizador já participou) para sugerir conteúdo semelhante ou
relevante, sem precisar de um motor externo nem de uma tabela nova de eventos.
"""

from app import db
from app.models.material import Material
from app.models.comunidade import ComunidadePost, ComunidadeResposta, ComunidadeTag


# ─────────────────────────────────────────── Materiais ───────────────────────

def materiais_relacionados(material, limite: int = 6):
    """Materiais semelhantes a um material específico — mesma disciplina
    (maior peso), categoria, instituição ou ano letivo. Só entra quem partilha
    pelo menos um critério; ordenado por relevância e depois por popularidade."""
    termos = [db.case((Material.disciplina.ilike(material.disciplina), 5), else_=0)]
    if material.categoria_id:
        termos.append(db.case((Material.categoria_id == material.categoria_id, 4), else_=0))
    if material.instituicao:
        termos.append(db.case((Material.instituicao.ilike(material.instituicao), 2), else_=0))
    if material.ano_letivo:
        termos.append(db.case((Material.ano_letivo == material.ano_letivo, 1), else_=0))

    score = termos[0]
    for t in termos[1:]:
        score = score + t

    return (
        Material.query
        .filter(Material.status == Material.STATUS_APROVADO, Material.id != material.id)
        .filter(score > 0)
        .order_by(score.desc(), Material.downloads.desc(), Material.criado_em.desc())
        .limit(limite)
        .all()
    )


def materiais_para_utilizador(user, limite: int = 6):
    """"Recomendado para ti" — materiais da mesma instituição/curso do
    utilizador (excluindo os que ele próprio enviou). Sem instituição/curso
    no perfil, ou sem resultados suficientes, completa com os mais populares."""
    base = Material.query.filter(
        Material.status == Material.STATUS_APROVADO,
        Material.autor_id != user.id,
    )

    resultado = []
    if user.instituicao or user.curso:
        termos = []
        if user.instituicao:
            termos.append(db.case((Material.instituicao.ilike(user.instituicao), 3), else_=0))
        if user.curso:
            termos.append(db.case((Material.curso.ilike(user.curso), 2), else_=0))
        score = termos[0]
        for t in termos[1:]:
            score = score + t
        resultado = (
            base.filter(score > 0)
            .order_by(score.desc(), Material.downloads.desc(), Material.criado_em.desc())
            .limit(limite)
            .all()
        )

    if len(resultado) < limite:
        ids_existentes = [m.id for m in resultado]
        extra_query = base
        if ids_existentes:
            extra_query = extra_query.filter(Material.id.notin_(ids_existentes))
        extra = (
            extra_query.order_by(Material.downloads.desc(), Material.criado_em.desc())
            .limit(limite - len(resultado))
            .all()
        )
        resultado += extra

    return resultado


# ─────────────────────────────────────────── Comunidade ──────────────────────

def posts_relacionados(post, limite: int = 5):
    """Publicações semelhantes a uma publicação específica — mesmo tipo ou
    tags partilhadas. Filtra por SQL um conjunto candidato razoável e pontua
    em Python (mais simples e legível do que compor a contagem de tags
    partilhadas em SQL puro, sem perder correção)."""
    tag_ids = {t.id for t in post.tags}
    query = ComunidadePost.query.filter(ComunidadePost.id != post.id)
    if tag_ids:
        query = query.filter(db.or_(
            ComunidadePost.tipo == post.tipo,
            ComunidadePost.tags.any(ComunidadeTag.id.in_(tag_ids)),
        ))
    else:
        query = query.filter(ComunidadePost.tipo == post.tipo)

    candidatos = query.order_by(ComunidadePost.criado_em.desc()).limit(200).all()

    def pontuar(p):
        pontos = 2 if p.tipo == post.tipo else 0
        pontos += len(tag_ids & {t.id for t in p.tags}) * 3
        pontos += min(max(p.votos_score, 0), 20) * 0.05
        return pontos

    candidatos = [p for p in candidatos if pontuar(p) > 0]
    candidatos.sort(key=pontuar, reverse=True)
    return candidatos[:limite]


def posts_para_utilizador(user, limite: int = 5):
    """"Publicações que podem interessar-te" — baseado nas tags dos posts em
    que o próprio utilizador já participou (autor ou respondeu), um sinal
    implícito de interesse sem precisar de tracking novo. Sem atividade
    prévia, cai para os mais votados/recentes."""
    ids_posts_autor = [
        r[0] for r in db.session.query(ComunidadePost.id).filter_by(autor_id=user.id).all()
    ]
    ids_posts_comentados = [
        r[0] for r in db.session.query(ComunidadeResposta.post_id).filter_by(autor_id=user.id).all()
    ]
    ids_envolvidos = set(ids_posts_autor) | set(ids_posts_comentados)

    tag_ids = set()
    if ids_envolvidos:
        for p in ComunidadePost.query.filter(ComunidadePost.id.in_(ids_envolvidos)).all():
            tag_ids.update(t.id for t in p.tags)

    base = ComunidadePost.query.filter(ComunidadePost.autor_id != user.id)
    if ids_envolvidos:
        base = base.filter(ComunidadePost.id.notin_(ids_envolvidos))

    resultado = []
    if tag_ids:
        candidatos = (
            base.filter(ComunidadePost.tags.any(ComunidadeTag.id.in_(tag_ids)))
            .order_by(ComunidadePost.criado_em.desc())
            .limit(200)
            .all()
        )

        def pontuar(p):
            return len(tag_ids & {t.id for t in p.tags}) * 3 + min(max(p.votos_score, 0), 20) * 0.05

        candidatos.sort(key=pontuar, reverse=True)
        resultado = candidatos[:limite]

    if len(resultado) < limite:
        ids_existentes = [p.id for p in resultado]
        extra_query = base
        if ids_existentes:
            extra_query = extra_query.filter(ComunidadePost.id.notin_(ids_existentes))
        extra = (
            extra_query.order_by(ComunidadePost.votos_score.desc(), ComunidadePost.criado_em.desc())
            .limit(limite - len(resultado))
            .all()
        )
        resultado += extra

    return resultado
