"""Sistema de badges (conquistas) do perfil.

Computado em tempo real a partir de contadores que já existem no modelo
(`User.total_uploads`, `User.total_downloads`) ou de queries simples
(downloads recebidos) — sem tabela de "desbloqueios" própria. Isto evita ter
de recalcular/repor um histórico em background: o badge nunca fica
desincronizado, é sempre um reflexo direto do estado atual.
"""

from app import db
from app.models.material import Material

# Ordem = ordem de exibição no perfil.
TIERS = ["bronze", "prata", "ouro", "diamante"]

TIERS_INFO = {
    "bronze":   {"nome": "Bronze",   "cor": "text-warning",   "bg": "bg-warning"},
    "prata":    {"nome": "Prata",    "cor": "text-secondary", "bg": "bg-secondary"},
    "ouro":     {"nome": "Ouro",     "cor": "text-orange",    "bg": "bg-orange"},
    "diamante": {"nome": "Diamante", "cor": "text-info",      "bg": "bg-info"},
}


def _downloads_recebidos(user) -> int:
    """Soma de downloads em todos os materiais enviados pelo utilizador."""
    total = db.session.query(
        db.func.coalesce(db.func.sum(Material.downloads), 0)
    ).filter(Material.autor_id == user.id).scalar()
    return total or 0


# Cada categoria: id, nome, ícone (bootstrap-icons), descrição curta, função
# que calcula o valor atual, e os limiares (mínimo, tier) em ordem crescente.
CATEGORIAS = [
    {
        "id": "contribuidor",
        "nome": "Contribuidor",
        "icone": "bi-journal-check",
        "descricao": "Materiais aprovados enviados",
        "getter": lambda user: user.total_uploads or 0,
        "limiares": [(1, "bronze"), (5, "prata"), (15, "ouro"), (40, "diamante")],
    },
    {
        "id": "estudioso",
        "nome": "Estudioso",
        "icone": "bi-download",
        "descricao": "Materiais descarregados",
        "getter": lambda user: user.total_downloads or 0,
        "limiares": [(5, "bronze"), (25, "prata"), (75, "ouro"), (200, "diamante")],
    },
    {
        "id": "popular",
        "nome": "Conteúdo Popular",
        "icone": "bi-fire",
        "descricao": "Downloads recebidos nos teus materiais",
        "getter": _downloads_recebidos,
        "limiares": [(10, "bronze"), (50, "prata"), (200, "ouro"), (1000, "diamante")],
    },
]


def badges_do_utilizador(user):
    """Devolve uma lista (uma entrada por categoria) com o tier mais alto já
    alcançado (ou None) e o próximo objetivo, para mostrar no perfil."""
    resultado = []
    for cat in CATEGORIAS:
        valor = cat["getter"](user) or 0
        tier_atual = None
        proximo = None
        for minimo, tier in cat["limiares"]:
            if valor >= minimo:
                tier_atual = tier
            elif proximo is None:
                proximo = {"minimo": minimo, "tier": tier, "faltam": minimo - valor}
        resultado.append({
            "id": cat["id"],
            "nome": cat["nome"],
            "icone": cat["icone"],
            "descricao": cat["descricao"],
            "valor": valor,
            "tier": tier_atual,
            "tier_info": TIERS_INFO.get(tier_atual),
            "proximo": proximo,
        })
    return resultado
