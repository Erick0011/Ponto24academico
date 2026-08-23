"""Recomendação de conteúdo — baseada em regras, não em histórico de
navegação: usa dados que já existem (disciplina/instituição/curso do perfil,
categoria/disciplina/instituição do material) para sugerir conteúdo semelhante
ou relevante, sem precisar de um motor externo nem de uma tabela nova de
eventos.
"""

from app import db
from app.models.material import Material


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
