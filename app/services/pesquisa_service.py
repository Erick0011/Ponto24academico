"""Pesquisa avançada com pontuação de relevância — compatível com SQLite e
Postgres: usa ILIKE + CASE/soma em vez de full-text nativo de um motor
específico, para se comportar da mesma forma em dev (SQLite) e produção
(Postgres, se vier a ser usado)."""

from app import db


def condicoes_e_pontuacao(termo: str, campos_pesos: list):
    """Constrói a condição de filtro e a expressão de pontuação para uma
    pesquisa multi-palavra sobre várias colunas com pesos diferentes.

    termo: string de pesquisa livre (pode ter várias palavras separadas por espaço).
    campos_pesos: lista de tuplos (coluna, peso) — cada palavra do termo soma
    `peso` pontos quando aparece nessa coluna (ILIKE, correspondência parcial).

    Devolve (condicao, pontuacao):
      - condicao: cada palavra tem de aparecer em pelo menos um dos campos
        (AND entre palavras, OR entre campos) — filtra fora o ruído, ex.
        "prova cálculo" só encontra registos com as duas palavras, nalgum
        campo cada uma, não necessariamente juntas nem no mesmo campo.
      - pontuacao: expressão SQL somável (soma dos pesos de todos os campos/
        palavras que corresponderam), usada para ordenar por relevância.

    Devolve (None, None) se o termo estiver vazio.
    """
    palavras = [p for p in termo.split() if p]
    if not palavras or not campos_pesos:
        return None, None

    condicoes_and = []
    pontos_por_palavra = []
    for palavra in palavras:
        like = f"%{palavra}%"
        condicoes_and.append(db.or_(*[coluna.ilike(like) for coluna, _ in campos_pesos]))

        pontos = None
        for coluna, peso in campos_pesos:
            termo_pontos = db.case((coluna.ilike(like), peso), else_=0)
            pontos = termo_pontos if pontos is None else pontos + termo_pontos
        pontos_por_palavra.append(pontos)

    pontuacao = pontos_por_palavra[0]
    for p in pontos_por_palavra[1:]:
        pontuacao = pontuacao + p

    return db.and_(*condicoes_and), pontuacao
