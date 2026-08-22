"""Ligações internas da Comunidade — tópicos e respostas podem referenciar
materiais, outros tópicos ou outras respostas. Três formas de ligar
(sintaxe curta no texto, colar um URL interno, ou escolher num "Anexar"
futuro) convergem todas no mesmo mecanismo: o texto guardado contém a
sintaxe curta (#123, @material:456); ao gravar, `sincronizar_links` lê-a e
grava em ComunidadeLink; ao mostrar, `renderizar_link_corpo` lê-a de novo e
substitui pelo cartão — nunca há duas fontes de verdade.

Nota de âmbito: um URL colado (ex. ".../comunidade/123") já é detetado e
convertido tal como a sintaxe curta (ver RE_URL_*), mas o botão "Anexar" com
pesquisa em modal ainda não tem UI própria — para já, liga-se escrevendo a
sintaxe curta diretamente ou colando o URL.
"""

import re
from markupsafe import Markup, escape
from flask import url_for
from app import db
from app.models.comunidade import ComunidadeLink, ComunidadePost, ComunidadeResposta
from app.models.material import Material

RE_TOPICO = re.compile(r"#(\d+)\b")
RE_MATERIAL = re.compile(r"@material:(\d+)\b")
RE_URL_TOPICO = re.compile(r"(?:https?://[^\s]+)?/comunidade/(\d+)(?:[/?][^\s]*)?")
RE_URL_MATERIAL = re.compile(r"(?:https?://[^\s]+)?/materiais/(\d+)(?:[/?][^\s]*)?")


def extrair_links(texto: str) -> set:
    """Devolve um set de (target_tipo, target_id) detetados no texto — sem
    validar se o alvo existe (isso é ao sincronizar/renderizar, onde já
    precisamos de ir à BD de qualquer forma)."""
    achados = set()
    if not texto:
        return achados
    for m in RE_TOPICO.finditer(texto):
        achados.add((ComunidadeLink.TARGET_TOPICO, int(m.group(1))))
    for m in RE_MATERIAL.finditer(texto):
        achados.add((ComunidadeLink.TARGET_MATERIAL, int(m.group(1))))
    for m in RE_URL_TOPICO.finditer(texto):
        achados.add((ComunidadeLink.TARGET_TOPICO, int(m.group(1))))
    for m in RE_URL_MATERIAL.finditer(texto):
        achados.add((ComunidadeLink.TARGET_MATERIAL, int(m.group(1))))
    return achados


def sincronizar_links(source_tipo: str, source_id: int, criado_por_id: int, texto: str):
    """Cria as ligações detetadas em `texto` que ainda não existem. Nunca
    remove ligações existentes (mesmo que a menção desapareça do texto numa
    edição) — evita apagar uma ligação anexada por outro caminho no futuro.
    Evita auto-referência e ligações para alvos inexistentes. O caller ainda
    tem de fazer db.session.commit()."""
    criados = []
    for target_tipo, target_id in extrair_links(texto):
        if source_tipo == target_tipo and source_id == target_id:
            continue  # nunca se liga a si próprio
        if target_tipo == ComunidadeLink.TARGET_MATERIAL and not Material.query.get(target_id):
            continue
        if target_tipo == ComunidadeLink.TARGET_TOPICO and not ComunidadePost.query.get(target_id):
            continue

        existente = ComunidadeLink.query.filter_by(
            source_tipo=source_tipo, source_id=source_id,
            target_tipo=target_tipo, target_id=target_id,
        ).first()
        if existente:
            continue
        link = ComunidadeLink(
            source_tipo=source_tipo, source_id=source_id,
            target_tipo=target_tipo, target_id=target_id,
            criado_por_id=criado_por_id,
        )
        db.session.add(link)
        criados.append(link)
    return criados


def _card_indisponivel() -> str:
    return (
        '<span class="comunidade-link-card comunidade-link-card--indisponivel">'
        '<i class="bi bi-slash-circle"></i> Conteúdo indisponível</span>'
    )


def _card_topico(post) -> str:
    href = url_for("comunidade.detalhe", id=post.id)
    titulo = escape(post.titulo)
    return (
        f'<a href="{href}" class="comunidade-link-card comunidade-link-card--topico">'
        f'<i class="bi bi-chat-left-text"></i> {titulo}</a>'
    )


def _card_material(material) -> str:
    href = url_for("materiais.detalhe", id=material.id)
    titulo = escape(material.titulo_base)
    meta = escape(f"{material.disciplina} · {material.instituicao}")
    return (
        f'<a href="{href}" class="comunidade-link-card comunidade-link-card--material">'
        f'<i class="bi bi-file-earmark-text"></i> <span>{titulo}<small>{meta}</small></span></a>'
    )


def renderizar_link_corpo(texto: str, utilizador=None) -> Markup:
    """Escapa `texto` (nunca confiar em HTML vindo do utilizador) e substitui
    a sintaxe curta detetada por cartões — permissões aplicadas no momento
    da renderização (material pendente/rejeitado só é visível ao autor ou a
    quem modera); alvo removido ou nunca existente mostra o estado
    degradado, nunca um link partido."""
    if not texto:
        return Markup("")

    texto_escapado = str(escape(texto))

    def sub_topico(m):
        post = ComunidadePost.query.get(int(m.group(1)))
        return _card_topico(post) if post else _card_indisponivel()

    def sub_material(m):
        material = Material.query.get(int(m.group(1)))
        if not material:
            return _card_indisponivel()
        e_autor = utilizador is not None and getattr(utilizador, "is_authenticated", False) and utilizador.id == material.autor_id
        pode_moderar = utilizador is not None and getattr(utilizador, "is_authenticated", False) and (
            utilizador.is_admin or getattr(utilizador, "is_moderador", False)
        )
        if not material.esta_aprovado and not e_autor and not pode_moderar:
            return _card_indisponivel()
        return _card_material(material)

    texto_escapado = RE_TOPICO.sub(sub_topico, texto_escapado)
    texto_escapado = RE_MATERIAL.sub(sub_material, texto_escapado)
    return Markup(texto_escapado)


def topicos_relacionados(target_tipo: str, target_id: int, limite: int = 10):
    """Tópicos (ComunidadePost) que mencionam este alvo — direto (o próprio
    post liga-se) ou indireto (uma resposta dentro dele liga-se). Usado em
    "Discutido em N tópicos" (material) e "Referenciado por" (tópico)."""
    links = ComunidadeLink.query.filter_by(target_tipo=target_tipo, target_id=target_id).all()
    post_ids = set()
    for link in links:
        if link.source_tipo == ComunidadeLink.SOURCE_TOPICO:
            post_ids.add(link.source_id)
        else:
            r = ComunidadeResposta.query.get(link.source_id)
            if r:
                post_ids.add(r.post_id)
    # Um tópico nunca se refere a "si próprio" na lista de relacionados.
    if target_tipo == ComunidadeLink.TARGET_TOPICO:
        post_ids.discard(target_id)
    if not post_ids:
        return []
    return (
        ComunidadePost.query.filter(ComunidadePost.id.in_(post_ids))
        .order_by(ComunidadePost.criado_em.desc())
        .limit(limite)
        .all()
    )
