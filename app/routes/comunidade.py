import re
import unicodedata
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify,
)
from flask_login import login_required, current_user
from app import db, limiter
from app.models.comunidade import (
    ComunidadePost, ComunidadePostImagem, ComunidadeResposta, ComunidadeRespostaImagem,
    ComunidadeVoto, ComunidadeRelatorio, ComunidadeTag, ComunidadeCategoria, ComunidadeSubscricao,
    ComunidadeReacao, ComunidadeLink,
)
from app.models.notificacao import Notificacao
from app.models.atividade import AtividadeLog
from app.services.atividade_service import registar_atividade
from app.services.notificacoes_service import criar_notificacao
from app.services.creditos_service import (
    dar_creditos_comunidade_post, dar_creditos_comunidade_resposta, dar_creditos_melhor_resposta,
)
from app.services.upload_service import guardar_ficheiro, apagar_ficheiro
from app.services.comunidade_service import aplicar_voto, voto_do_utilizador, feed_query, anuncios_fixados_ativos
from app.services.comunidade_reacoes_service import alternar_reacao, reacoes_de
from app.services.comunidade_links_service import sincronizar_links, topicos_relacionados
from app.services.comunidade_auditoria_service import registar_auditoria_evento
from app.services.recomendacao_service import posts_relacionados
from app.utils.honeypot import honeypot_preenchido

comunidade_bp = Blueprint("comunidade", __name__, url_prefix="/comunidade")

# Janela em que o próprio autor pode editar o que escreveu (depois disso, só
# um moderador). Passado este prazo o conteúdo já pode ter respostas/votos
# que dependem dele, por isso deixa de ser seguro deixar editar livremente.
JANELA_EDICAO = timedelta(minutes=15)


def _dentro_da_janela_edicao(criado_em) -> bool:
    return datetime.utcnow() - criado_em <= JANELA_EDICAO


def _pode_editar(obj) -> bool:
    """`obj` é um ComunidadePost ou ComunidadeResposta — mesma regra para os
    dois: o autor pode editar dentro da janela de tempo; quem modera, sempre."""
    if not current_user.is_authenticated:
        return False
    if _pode_moderar():
        return True
    return obj.autor_id == current_user.id and _dentro_da_janela_edicao(obj.criado_em)


def _subscrever(utilizador_id: int, post_id: int):
    """Subscreve (idempotente) um utilizador a um tópico — chamado ao criar o
    post (autor) e ao responder-lhe (interesse implícito). Não faz commit,
    o caller já commita a seguir."""
    existe = ComunidadeSubscricao.query.filter_by(utilizador_id=utilizador_id, post_id=post_id).first()
    if not existe:
        db.session.add(ComunidadeSubscricao(utilizador_id=utilizador_id, post_id=post_id))


def _truncar(texto, limite=157):
    """Corta texto no limite de caracteres sem partir palavras (para meta description)."""
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",.;") + "…"


def _pode_moderar() -> bool:
    return current_user.is_authenticated and (current_user.is_admin or current_user.is_moderador)


def _tipos_disponiveis():
    """"Aviso" só pode ser escolhido por quem modera — é o canal de
    comunicados oficiais da equipa, não uma etiqueta livre para qualquer post.
    Mantido por compatibilidade — o formulário de criação já usa categorias
    (ver _categorias_disponiveis); isto ainda serve o filtro `tipo` legado."""
    if _pode_moderar():
        return ComunidadePost.TIPOS
    return [t for t in ComunidadePost.TIPOS if t[0] != ComunidadePost.TIPO_AVISO]


def _categorias_disponiveis():
    """Categorias ativas em que o utilizador atual pode publicar — as
    marcadas "apenas_admin" (ex: Anúncios) só aparecem para quem modera."""
    todas = ComunidadeCategoria.query.filter_by(ativa=True).order_by(
        ComunidadeCategoria.ordem, ComunidadeCategoria.nome
    ).all()
    if _pode_moderar():
        return todas
    return [c for c in todas if not c.apenas_admin]


def _slugify_tag(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.strip().lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:40]


def _obter_ou_criar_tags(bruto: str, limite: int = 5):
    """Converte "cálculo, provas, exame" em ComunidadeTag existentes ou novas
    (folksonomia — sem curadoria de admin)."""
    nomes = [n.strip() for n in (bruto or "").split(",")]
    nomes = [n for n in nomes if n][:limite]
    tags, vistos = [], set()
    for nome in nomes:
        slug = _slugify_tag(nome)
        if not slug or slug in vistos:
            continue
        vistos.add(slug)
        tag = ComunidadeTag.query.filter_by(slug=slug).first()
        if not tag:
            tag = ComunidadeTag(slug=slug, nome=nome[:40])
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    return tags


@comunidade_bp.route("/")
def feed():
    tipo = request.args.get("tipo", "").strip() or None  # filtro legado, ver feed_query()
    categoria = request.args.get("categoria", "").strip() or None
    tag = request.args.get("tag", "").strip() or None
    busca = request.args.get("q", "").strip()
    ordenar = request.args.get("ordenar", "recentes")
    page = request.args.get("page", 1, type=int)

    posts = feed_query(tipo=tipo, categoria=categoria, tag=tag, busca=busca, ordenar=ordenar).paginate(page=page, per_page=12, error_out=False)

    votos_posts = {}
    if current_user.is_authenticated:
        for p in posts.items:
            votos_posts[p.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_POST, p.id)

    if request.args.get("fragmento"):
        # Scroll infinito — devolve só o HTML dos cartões desta página, para o
        # JS do feed anexar ao fim da lista (ver comunidade/feed.html).
        html = render_template("comunidade/_post_cards.html", posts=posts.items, votos_posts=votos_posts)
        return jsonify(html=html, tem_mais=posts.has_next, proxima_pagina=posts.next_num)

    categorias_filtro = ComunidadeCategoria.query.filter_by(ativa=True).order_by(
        ComunidadeCategoria.ordem, ComunidadeCategoria.nome
    ).all()
    categoria_nome_filtro = next((c.nome for c in categorias_filtro if c.slug == categoria), categoria)

    return render_template(
        "comunidade/feed.html", posts=posts, tipo=tipo, categoria=categoria, tag=tag, busca=busca, ordenar=ordenar,
        tipos=ComunidadePost.TIPOS, tipos_dict=dict(ComunidadePost.TIPOS),
        categorias_filtro=categorias_filtro, categoria_nome_filtro=categoria_nome_filtro,
        votos_posts=votos_posts, anuncios_fixados=anuncios_fixados_ativos(),
    )


@comunidade_bp.route("/novo", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour", methods=["POST"])
def criar_post():
    if current_user.suspenso_da_comunidade:
        flash("A tua conta está suspensa na Comunidade e não podes publicar.", "erro")
        return redirect(url_for("comunidade.feed"))

    if request.method == "POST":
        if honeypot_preenchido():
            flash("Não foi possível publicar. Tenta novamente.", "erro")
            return redirect(url_for("comunidade.feed"))

        titulo = request.form.get("titulo", "").strip()
        corpo = request.form.get("corpo", "").strip()

        categoria_id = request.form.get("categoria_id", type=int)
        categoria = ComunidadeCategoria.query.get(categoria_id) if categoria_id else None
        if categoria and categoria.apenas_admin and not _pode_moderar():
            flash("Só a equipa pode publicar em Anúncios — escolhe outra categoria.", "aviso")
            categoria = None
        if not categoria or not categoria.ativa:
            # Sem categoria válida escolhida: cai em "Geral" se existir, para
            # nunca bloquear a publicação por causa disto.
            categoria = ComunidadeCategoria.query.filter_by(slug="geral", ativa=True).first()
        # `tipo` legado, derivado da categoria — mantém a filtragem/():badge
        # antigos (post.tipo == 'aviso') a funcionar sem alterações.
        tipo = ComunidadePost.TIPO_AVISO if (categoria and categoria.apenas_admin) else ComunidadePost.TIPO_DISCUSSAO

        if not titulo or not corpo:
            flash("Preenche o título e o conteúdo da publicação.", "erro")
            return render_template("comunidade/post_form.html", categorias=_categorias_disponiveis())

        post = ComunidadePost(
            titulo=titulo, corpo=corpo, tipo=tipo, autor_id=current_user.id,
            categoria_id=categoria.id if categoria else None,
        )
        post.tags = _obter_ou_criar_tags(request.form.get("tags", ""))
        db.session.add(post)
        db.session.flush()
        _subscrever(current_user.id, post.id)  # autor fica subscrito automaticamente
        sincronizar_links(ComunidadeLink.SOURCE_TOPICO, post.id, current_user.id, corpo)

        imagens = [f for f in request.files.getlist("imagens") if f.filename != ""]
        ano, mes = datetime.now().strftime("%Y"), datetime.now().strftime("%m")
        subfolder = f"comunidade/{ano}/{mes}"
        for f in imagens[:6]:  # limite razoável por post
            try:
                info = guardar_ficheiro(f, subfolder=subfolder)
            except ValueError:
                continue  # ignora ficheiros com extensão não permitida, não bloqueia o post
            db.session.add(ComunidadePostImagem(post_id=post.id, path_relativo=info["path_relativo"]))

        registar_atividade(
            AtividadeLog.EVENTO_COMUNIDADE_POST_CRIADO,
            utilizador_id=current_user.id, alvo_tipo="comunidade_post", alvo_id=post.id,
            detalhes={"titulo": titulo, "tipo": tipo, "categoria": categoria.slug if categoria else None},
        )
        db.session.commit()
        dar_creditos_comunidade_post(current_user)

        flash("Publicação criada!", "sucesso")
        return redirect(url_for("comunidade.detalhe", id=post.id))

    return render_template("comunidade/post_form.html", categorias=_categorias_disponiveis())


@comunidade_bp.route("/<int:id>")
def detalhe(id):
    post = ComunidadePost.query.get_or_404(id)
    page = request.args.get("page", 1, type=int)
    ordenar = request.args.get("ordenar", "recentes")

    # Só o nível de topo é paginado — as réplicas (1 nível) vêm sempre juntas
    # com o comentário-pai, senão a paginação partia threads a meio.
    query = post.respostas.filter_by(parent_id=None)
    if ordenar == "votados":
        query = query.order_by(ComunidadeResposta.votos_score.desc(), ComunidadeResposta.criado_em.asc())
    else:
        query = query.order_by(ComunidadeResposta.criado_em.asc())
    respostas = query.paginate(page=page, per_page=20, error_out=False)

    voto_post = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_POST, post.id)
    votos_respostas = {}
    pode_editar_respostas = {}
    resposta_ids = []
    if current_user.is_authenticated:
        for r in respostas.items:
            votos_respostas[r.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_RESPOSTA, r.id)
            pode_editar_respostas[r.id] = _pode_editar(r)
            for rep in r.replicas:
                votos_respostas[rep.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_RESPOSTA, rep.id)
                pode_editar_respostas[rep.id] = _pode_editar(rep)
    for r in respostas.items:
        resposta_ids.append(r.id)
        resposta_ids.extend(rep.id for rep in r.replicas)

    reacoes_post_n, reacoes_post_minhas = reacoes_de(ComunidadeReacao.ALVO_POST, [post.id], current_user)
    reacoes_resp_n, reacoes_resp_minhas = reacoes_de(ComunidadeReacao.ALVO_RESPOSTA, resposta_ids, current_user)

    meta_descricao = _truncar(post.corpo) or f"Publicação de {post.autor.nome} na Comunidade Ponto 24 Académico."
    pode_moderar = _pode_moderar()
    esta_subscrito = current_user.is_authenticated and ComunidadeSubscricao.query.filter_by(
        utilizador_id=current_user.id, post_id=post.id
    ).first() is not None

    return render_template(
        "comunidade/detalhe.html", post=post, respostas=respostas, ordenar=ordenar,
        voto_post=voto_post, votos_respostas=votos_respostas, pode_moderar=pode_moderar,
        pode_editar_post=_pode_editar(post), pode_editar_respostas=pode_editar_respostas,
        esta_subscrito=esta_subscrito,
        reacoes_tipos=ComunidadeReacao.TIPOS, reacoes_icones=ComunidadeReacao.ICONES,
        reacoes_post_n=reacoes_post_n.get(post.id, {}), reacoes_post_minhas=reacoes_post_minhas.get(post.id, set()),
        reacoes_resp_n=reacoes_resp_n, reacoes_resp_minhas=reacoes_resp_minhas,
        referenciado_por=topicos_relacionados(ComunidadeLink.TARGET_TOPICO, post.id),
        meta_descricao=meta_descricao,
        motivos=ComunidadeRelatorio.MOTIVOS,
        estados=ComunidadePost.ESTADOS,
        relacionados=posts_relacionados(post),
    )


@comunidade_bp.route("/<int:id>/responder", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def criar_resposta(id):
    post = ComunidadePost.query.get_or_404(id)
    if current_user.suspenso_da_comunidade:
        flash("A tua conta está suspensa na Comunidade e não podes responder.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))
    if post.estado == ComunidadePost.ESTADO_FECHADO and not _pode_moderar():
        flash("Esta publicação está fechada e já não aceita novas respostas.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))
    if honeypot_preenchido():
        flash("Não foi possível publicar a resposta. Tenta novamente.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))

    corpo = request.form.get("corpo", "").strip()
    imagens = [f for f in request.files.getlist("imagens") if f.filename != ""]
    if not corpo and not imagens:
        flash("Escreve uma resposta ou anexa uma foto antes de enviar.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))

    # Réplica a um comentário (1 nível só): se o alvo já for ele próprio uma
    # réplica, a nova resposta "sobe" para ficar sob o comentário de topo.
    parent = None
    parent_id = request.form.get("parent_id", type=int)
    if parent_id:
        parent = ComunidadeResposta.query.filter_by(id=parent_id, post_id=post.id).first()
        if parent and parent.parent_id is not None:
            parent = parent.parent

    resposta = ComunidadeResposta(
        post_id=post.id, parent_id=parent.id if parent else None,
        autor_id=current_user.id, corpo=corpo,
    )
    db.session.add(resposta)
    db.session.flush()

    ano, mes = datetime.now().strftime("%Y"), datetime.now().strftime("%m")
    subfolder = f"comunidade/respostas/{ano}/{mes}"
    for f in imagens[:4]:  # limite razoável por comentário
        try:
            info = guardar_ficheiro(f, subfolder=subfolder)
        except ValueError:
            continue  # ignora ficheiros com extensão não permitida, não bloqueia a resposta
        db.session.add(ComunidadeRespostaImagem(resposta_id=resposta.id, path_relativo=info["path_relativo"]))

    post.respostas_count += 1
    _subscrever(current_user.id, post.id)  # quem responde passa a seguir o tópico
    sincronizar_links(ComunidadeLink.SOURCE_RESPOSTA, resposta.id, current_user.id, corpo)

    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_RESPOSTA_CRIADA,
        utilizador_id=current_user.id, alvo_tipo="comunidade_resposta", alvo_id=post.id,
        detalhes={"post_id": post.id},
    )

    # Notificações — mensagem específica para quem foi diretamente respondido
    # (o autor do comentário-pai, o autor do tópico); todos os outros
    # subscritores (quem seguiu o tópico sem ter respondido) recebem a
    # genérica. `ja_notificados` evita duplicar notificação para a mesma
    # pessoa por dois motivos ao mesmo tempo.
    ja_notificados = {current_user.id}
    if parent and parent.autor_id not in ja_notificados:
        criar_notificacao(
            utilizador_id=parent.autor_id,
            tipo=Notificacao.TIPO_COMUNIDADE_RESPOSTA,
            titulo="Alguém respondeu ao teu comentário",
            mensagem=f"{current_user.nome.split()[0]} respondeu-te em \"{post.titulo}\".",
            url=url_for("comunidade.detalhe", id=post.id),
        )
        ja_notificados.add(parent.autor_id)
    if post.autor_id not in ja_notificados:
        criar_notificacao(
            utilizador_id=post.autor_id,
            tipo=Notificacao.TIPO_COMUNIDADE_RESPOSTA,
            titulo="Nova resposta à tua publicação",
            mensagem=f"{current_user.nome.split()[0]} respondeu a \"{post.titulo}\".",
            url=url_for("comunidade.detalhe", id=post.id),
        )
        ja_notificados.add(post.autor_id)

    subscritores_ids = {s.utilizador_id for s in post.subscricoes.all()} - ja_notificados
    for uid in subscritores_ids:
        criar_notificacao(
            utilizador_id=uid,
            tipo=Notificacao.TIPO_COMUNIDADE_RESPOSTA,
            titulo="Nova resposta num tópico que segues",
            mensagem=f"{current_user.nome.split()[0]} respondeu em \"{post.titulo}\".",
            url=url_for("comunidade.detalhe", id=post.id),
        )

    db.session.commit()
    dar_creditos_comunidade_resposta(current_user)

    flash("Resposta publicada!", "sucesso")
    return redirect(url_for("comunidade.detalhe", id=id))


@comunidade_bp.route("/<int:id>/estado", methods=["POST"])
@login_required
def mudar_estado_post(id):
    """Marca o tópico como resolvido/fechado/aberto de novo — o autor do
    tópico ou um moderador. "Pedidos de material" usa isto como o próprio
    fluxo de conclusão, sem precisar de um sistema à parte."""
    post = ComunidadePost.query.get_or_404(id)
    if post.autor_id != current_user.id and not _pode_moderar():
        abort(403)

    novo_estado = request.form.get("estado", "")
    if novo_estado not in dict(ComunidadePost.ESTADOS):
        flash("Estado inválido.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))

    post.estado = novo_estado
    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_ESTADO_ALTERADO,
        utilizador_id=current_user.id, alvo_tipo="comunidade_post", alvo_id=post.id,
        detalhes={"estado": novo_estado},
    )
    db.session.commit()
    flash(f"Publicação marcada como \"{post.estado_label}\".", "sucesso")
    return redirect(url_for("comunidade.detalhe", id=id))


@comunidade_bp.route("/respostas/<int:id>/marcar-melhor", methods=["POST"])
@login_required
def marcar_melhor_resposta(id):
    """O autor do tópico (ou um moderador) marca/desmarca a melhor resposta.
    Marcar move o tópico automaticamente para "resolvido" e dá créditos a
    quem respondeu (função já existente em creditos_service)."""
    resposta = ComunidadeResposta.query.get_or_404(id)
    post = resposta.post
    if post.autor_id != current_user.id and not _pode_moderar():
        abort(403)
    if resposta.parent_id is not None:
        flash("Só uma resposta de topo pode ser marcada como melhor resposta.", "erro")
        return redirect(url_for("comunidade.detalhe", id=post.id))

    ja_era = post.melhor_resposta_id == resposta.id
    if ja_era:
        post.melhor_resposta_id = None
        mensagem = "Melhor resposta removida."
    else:
        post.melhor_resposta_id = resposta.id
        post.estado = ComunidadePost.ESTADO_RESOLVIDO
        mensagem = "Marcada como melhor resposta!"
        if resposta.autor_id != current_user.id:
            dar_creditos_melhor_resposta(resposta.autor)
            criar_notificacao(
                utilizador_id=resposta.autor_id,
                tipo=Notificacao.TIPO_COMUNIDADE_MELHOR_RESPOSTA,
                titulo="A tua resposta foi marcada como melhor resposta!",
                mensagem=f"Em \"{post.titulo}\" — ganhaste créditos por isso.",
                url=url_for("comunidade.detalhe", id=post.id),
            )

    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_MELHOR_RESPOSTA,
        utilizador_id=current_user.id, alvo_tipo="comunidade_resposta", alvo_id=resposta.id,
        detalhes={"post_id": post.id, "marcada": not ja_era},
    )
    db.session.commit()
    flash(mensagem, "sucesso")
    return redirect(url_for("comunidade.detalhe", id=post.id))


@comunidade_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_post(id):
    post = ComunidadePost.query.get_or_404(id)
    if not _pode_editar(post):
        if post.autor_id == current_user.id:
            flash("Já não podes editar esta publicação — passaram mais de 15 minutos.", "erro")
        else:
            abort(403)
        return redirect(url_for("comunidade.detalhe", id=id))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        corpo = request.form.get("corpo", "").strip()
        if not titulo or not corpo:
            flash("Preenche o título e o conteúdo da publicação.", "erro")
            return render_template("comunidade/post_editar.html", post=post)

        post.titulo, post.corpo = titulo, corpo
        post.editado = True
        post.tags = _obter_ou_criar_tags(request.form.get("tags", ", ".join(t.nome for t in post.tags)))
        sincronizar_links(ComunidadeLink.SOURCE_TOPICO, post.id, current_user.id, corpo)
        registar_atividade(
            AtividadeLog.EVENTO_COMUNIDADE_POST_EDITADO,
            utilizador_id=current_user.id, alvo_tipo="comunidade_post", alvo_id=post.id,
        )
        db.session.commit()
        flash("Publicação atualizada.", "sucesso")
        return redirect(url_for("comunidade.detalhe", id=id))

    return render_template("comunidade/post_editar.html", post=post)


@comunidade_bp.route("/respostas/<int:id>/editar", methods=["POST"])
@login_required
def editar_resposta(id):
    resposta = ComunidadeResposta.query.get_or_404(id)
    if not _pode_editar(resposta):
        if resposta.autor_id == current_user.id:
            flash("Já não podes editar esta resposta — passaram mais de 15 minutos.", "erro")
        else:
            abort(403)
        return redirect(url_for("comunidade.detalhe", id=resposta.post_id))

    corpo = request.form.get("corpo", "").strip()
    if not corpo:
        flash("O comentário não pode ficar vazio.", "erro")
        return redirect(url_for("comunidade.detalhe", id=resposta.post_id))

    resposta.corpo = corpo
    resposta.editado = True
    sincronizar_links(ComunidadeLink.SOURCE_RESPOSTA, resposta.id, current_user.id, corpo)
    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_RESPOSTA_EDITADA,
        utilizador_id=current_user.id, alvo_tipo="comunidade_resposta", alvo_id=resposta.id,
    )
    db.session.commit()
    flash("Resposta atualizada.", "sucesso")
    return redirect(url_for("comunidade.detalhe", id=resposta.post_id))


@comunidade_bp.route("/<int:id>/subscrever", methods=["POST"])
@login_required
def alternar_subscricao(id):
    """Seguir/deixar de seguir um tópico — recebe notificação de qualquer
    resposta nova, mesmo sem ter respondido. O autor e quem responde já
    ficam subscritos automaticamente (ver _subscrever); isto é para quem só
    quer acompanhar."""
    post = ComunidadePost.query.get_or_404(id)
    existente = ComunidadeSubscricao.query.filter_by(utilizador_id=current_user.id, post_id=post.id).first()
    if existente:
        db.session.delete(existente)
        mensagem = "Deixaste de seguir esta publicação."
    else:
        db.session.add(ComunidadeSubscricao(utilizador_id=current_user.id, post_id=post.id))
        mensagem = "Agora segues esta publicação — recebes notificação de novas respostas."
    db.session.commit()
    flash(mensagem, "sucesso")
    return redirect(url_for("comunidade.detalhe", id=id))


def _pedido_json() -> bool:
    """O JS da Comunidade marca os pedidos de voto com este cabeçalho. Sem ele
    (JS desligado, browser antigo) o formulário continua a funcionar à moda
    antiga, com POST + redirect — daí valer a pena manter os dois caminhos."""
    return request.headers.get("X-Requested-With") == "fetch"


def _votar(alvo_tipo, alvo_obj, redirect_endpoint, redirect_kwargs):
    # Volta para onde o voto foi disparado (feed ou detalhe) em vez de forçar
    # sempre a navegação para a página do post — melhor UX ao votar a partir
    # do feed, onde só se quer atualizar o número, não sair da lista.
    destino = request.referrer or url_for(redirect_endpoint, **redirect_kwargs)
    ajax = _pedido_json()

    def falhar(mensagem, categoria, codigo):
        if ajax:
            return jsonify({"ok": False, "erro": mensagem}), codigo
        flash(mensagem, categoria)
        return redirect(destino)

    if current_user.id == alvo_obj.autor_id:
        return falhar("Não podes votar no teu próprio conteúdo.", "aviso", 403)

    valor = request.form.get("valor", type=int)
    if valor not in (1, -1):
        return falhar("Voto inválido.", "erro", 400)

    aplicar_voto(current_user, alvo_tipo, alvo_obj.id, alvo_obj, valor)
    db.session.commit()

    if ajax:
        return jsonify({
            "ok": True,
            "score": alvo_obj.votos_score,
            # Depois do toggle/troca, qual é o voto que ficou (1, -1 ou None) —
            # é o que o JS precisa para pintar as setas sem recarregar.
            "meu_voto": voto_do_utilizador(current_user, alvo_tipo, alvo_obj.id),
        })
    return redirect(destino)


@comunidade_bp.route("/<int:id>/votar", methods=["POST"])
@login_required
def votar_post(id):
    post = ComunidadePost.query.get_or_404(id)
    return _votar(ComunidadeVoto.ALVO_POST, post, "comunidade.detalhe", {"id": post.id})


@comunidade_bp.route("/respostas/<int:id>/votar", methods=["POST"])
@login_required
def votar_resposta(id):
    resposta = ComunidadeResposta.query.get_or_404(id)
    return _votar(ComunidadeVoto.ALVO_RESPOSTA, resposta, "comunidade.detalhe", {"id": resposta.post_id})


@comunidade_bp.route("/reagir", methods=["POST"])
@login_required
def reagir():
    """Reação nomeada (Útil/Obrigado/Resolvido) a um post ou resposta — a par
    do voto genérico, não em substituição. Alterna: clicar de novo remove."""
    alvo_tipo = request.form.get("alvo_tipo", "")
    alvo_id = request.form.get("alvo_id", type=int)
    tipo = request.form.get("tipo", "")
    destino = request.referrer or url_for("comunidade.feed")

    if alvo_tipo not in (ComunidadeReacao.ALVO_POST, ComunidadeReacao.ALVO_RESPOSTA) or tipo not in dict(ComunidadeReacao.TIPOS):
        abort(400)

    if alvo_tipo == ComunidadeReacao.ALVO_POST:
        alvo = ComunidadePost.query.get_or_404(alvo_id)
    else:
        alvo = ComunidadeResposta.query.get_or_404(alvo_id)

    ligada = alternar_reacao(current_user, alvo_tipo, alvo_id, tipo)
    db.session.commit()
    return redirect(destino)


def _denunciar(alvo_tipo, alvo_id, redirect_endpoint, redirect_kwargs):
    motivo = request.form.get("motivo", "").strip()
    descricao = request.form.get("descricao", "").strip()
    if not motivo:
        flash("Seleciona o motivo da denúncia.", "erro")
        return redirect(url_for(redirect_endpoint, **redirect_kwargs))

    ja_denunciou = ComunidadeRelatorio.query.filter_by(
        alvo_tipo=alvo_tipo, alvo_id=alvo_id, autor_id=current_user.id,
        status=ComunidadeRelatorio.STATUS_PENDENTE,
    ).first()
    if ja_denunciou:
        flash("Já denunciaste este conteúdo. A equipa vai analisar.", "aviso")
        return redirect(url_for(redirect_endpoint, **redirect_kwargs))

    db.session.add(ComunidadeRelatorio(
        alvo_tipo=alvo_tipo, alvo_id=alvo_id, autor_id=current_user.id,
        motivo=motivo, descricao=descricao,
    ))
    db.session.commit()
    flash("Denúncia enviada. A equipa de moderação irá analisar em breve.", "sucesso")
    return redirect(url_for(redirect_endpoint, **redirect_kwargs))


@comunidade_bp.route("/<int:id>/denunciar", methods=["POST"])
@login_required
def denunciar_post(id):
    post = ComunidadePost.query.get_or_404(id)
    return _denunciar(ComunidadeVoto.ALVO_POST, post.id, "comunidade.detalhe", {"id": post.id})


@comunidade_bp.route("/respostas/<int:id>/denunciar", methods=["POST"])
@login_required
def denunciar_resposta(id):
    resposta = ComunidadeResposta.query.get_or_404(id)
    return _denunciar(ComunidadeVoto.ALVO_RESPOSTA, resposta.id, "comunidade.detalhe", {"id": resposta.post_id})


def eliminar_post_interno(post: ComunidadePost):
    """Elimina um post e as suas imagens do disco/R2. Reutilizado pela rota
    pública (autor) e pela fila de denúncias do admin (moderador)."""
    for img in post.imagens.all():
        apagar_ficheiro(img.path_relativo)
    db.session.delete(post)


def eliminar_resposta_interno(resposta: ComunidadeResposta):
    """Elimina uma resposta e as suas imagens do disco/R2 — incluindo as das
    réplicas, que o model apaga em cascata da BD mas cujos ficheiros não se
    apagam sozinhos. Reutilizado pela rota pública (autor) e pela fila de
    denúncias do admin (moderador)."""
    for r in [resposta] + list(resposta.replicas):
        for img in r.imagens.all():
            apagar_ficheiro(img.path_relativo)
    db.session.delete(resposta)


@comunidade_bp.route("/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_post(id):
    post = ComunidadePost.query.get_or_404(id)
    if post.autor_id != current_user.id and not _pode_moderar():
        abort(403)

    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_POST_ELIMINADO,
        utilizador_id=current_user.id, alvo_tipo="comunidade_post", alvo_id=post.id,
        detalhes={"titulo": post.titulo},
    )
    eliminar_post_interno(post)
    db.session.commit()
    flash("Publicação eliminada.", "aviso")
    return redirect(url_for("comunidade.feed"))


@comunidade_bp.route("/respostas/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_resposta(id):
    resposta = ComunidadeResposta.query.get_or_404(id)
    if resposta.autor_id != current_user.id and not _pode_moderar():
        abort(403)

    post_id = resposta.post_id
    post = ComunidadePost.query.get(post_id)
    # Eliminar um comentário de topo arrasta consigo as réplicas (cascade do modelo) —
    # o contador do post tem de descer o mesmo número.
    total_eliminado = 1 + resposta.replicas.count()
    if post:
        post.respostas_count = max(0, post.respostas_count - total_eliminado)

    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_RESPOSTA_ELIMINADA,
        utilizador_id=current_user.id, alvo_tipo="comunidade_resposta", alvo_id=resposta.id,
        detalhes={"post_id": post_id},
    )
    eliminar_resposta_interno(resposta)
    db.session.commit()
    flash("Resposta eliminada.", "aviso")
    return redirect(url_for("comunidade.detalhe", id=post_id))
