import re
import unicodedata
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
)
from flask_login import login_required, current_user
from app import db, limiter
from app.models.comunidade import (
    ComunidadePost, ComunidadePostImagem, ComunidadeResposta,
    ComunidadeVoto, ComunidadeRelatorio, ComunidadeTag,
)
from app.models.notificacao import Notificacao
from app.models.atividade import AtividadeLog
from app.services.atividade_service import registar_atividade
from app.services.notificacoes_service import criar_notificacao
from app.services.creditos_service import dar_creditos_comunidade_post, dar_creditos_comunidade_resposta
from app.services.upload_service import guardar_ficheiro, apagar_ficheiro
from app.services.comunidade_service import aplicar_voto, voto_do_utilizador, feed_query
from app.services.recomendacao_service import posts_relacionados
from app.utils.honeypot import honeypot_preenchido

comunidade_bp = Blueprint("comunidade", __name__, url_prefix="/comunidade")


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
    comunicados oficiais da equipa, não uma etiqueta livre para qualquer post."""
    if _pode_moderar():
        return ComunidadePost.TIPOS
    return [t for t in ComunidadePost.TIPOS if t[0] != ComunidadePost.TIPO_AVISO]


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
    tipo = request.args.get("tipo", "").strip() or None
    tag = request.args.get("tag", "").strip() or None
    busca = request.args.get("q", "").strip()
    ordenar = request.args.get("ordenar", "recentes")
    page = request.args.get("page", 1, type=int)

    posts = feed_query(tipo=tipo, tag=tag, busca=busca, ordenar=ordenar).paginate(page=page, per_page=12, error_out=False)

    votos_posts = {}
    if current_user.is_authenticated:
        for p in posts.items:
            votos_posts[p.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_POST, p.id)

    return render_template(
        "comunidade/feed.html", posts=posts, tipo=tipo, tag=tag, busca=busca, ordenar=ordenar,
        tipos=ComunidadePost.TIPOS, votos_posts=votos_posts,
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
        tipo = request.form.get("tipo", ComunidadePost.TIPO_DISCUSSAO)
        if tipo not in dict(ComunidadePost.TIPOS):
            tipo = ComunidadePost.TIPO_DISCUSSAO
        if tipo == ComunidadePost.TIPO_AVISO and not _pode_moderar():
            flash("Só a equipa pode publicar Avisos oficiais — a tua publicação foi criada como Discussão.", "aviso")
            tipo = ComunidadePost.TIPO_DISCUSSAO

        if not titulo or not corpo:
            flash("Preenche o título e o conteúdo da publicação.", "erro")
            return render_template("comunidade/post_form.html", tipos=_tipos_disponiveis())

        post = ComunidadePost(titulo=titulo, corpo=corpo, tipo=tipo, autor_id=current_user.id)
        post.tags = _obter_ou_criar_tags(request.form.get("tags", ""))
        db.session.add(post)
        db.session.flush()

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
            detalhes={"titulo": titulo, "tipo": tipo},
        )
        db.session.commit()
        dar_creditos_comunidade_post(current_user)

        flash("Publicação criada!", "sucesso")
        return redirect(url_for("comunidade.detalhe", id=post.id))

    return render_template("comunidade/post_form.html", tipos=_tipos_disponiveis())


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
    if current_user.is_authenticated:
        for r in respostas.items:
            votos_respostas[r.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_RESPOSTA, r.id)
            for rep in r.replicas:
                votos_respostas[rep.id] = voto_do_utilizador(current_user, ComunidadeVoto.ALVO_RESPOSTA, rep.id)

    meta_descricao = _truncar(post.corpo) or f"Publicação de {post.autor.nome} na Comunidade Ponto 24 Académico."

    return render_template(
        "comunidade/detalhe.html", post=post, respostas=respostas, ordenar=ordenar,
        voto_post=voto_post, votos_respostas=votos_respostas, pode_moderar=_pode_moderar(),
        meta_descricao=meta_descricao,
        motivos=ComunidadeRelatorio.MOTIVOS,
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
    if honeypot_preenchido():
        flash("Não foi possível publicar a resposta. Tenta novamente.", "erro")
        return redirect(url_for("comunidade.detalhe", id=id))

    corpo = request.form.get("corpo", "").strip()
    if not corpo:
        flash("Escreve uma resposta antes de enviar.", "erro")
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
    post.respostas_count += 1

    registar_atividade(
        AtividadeLog.EVENTO_COMUNIDADE_RESPOSTA_CRIADA,
        utilizador_id=current_user.id, alvo_tipo="comunidade_resposta", alvo_id=post.id,
        detalhes={"post_id": post.id},
    )

    if parent and parent.autor_id not in (current_user.id, post.autor_id):
        criar_notificacao(
            utilizador_id=parent.autor_id,
            tipo=Notificacao.TIPO_COMUNIDADE_RESPOSTA,
            titulo="Alguém respondeu ao teu comentário",
            mensagem=f"{current_user.nome.split()[0]} respondeu-te em \"{post.titulo}\".",
            url=url_for("comunidade.detalhe", id=post.id),
        )
    if post.autor_id != current_user.id:
        criar_notificacao(
            utilizador_id=post.autor_id,
            tipo=Notificacao.TIPO_COMUNIDADE_RESPOSTA,
            titulo="Nova resposta à tua publicação",
            mensagem=f"{current_user.nome.split()[0]} respondeu a \"{post.titulo}\".",
            url=url_for("comunidade.detalhe", id=post.id),
        )

    db.session.commit()
    dar_creditos_comunidade_resposta(current_user)

    flash("Resposta publicada!", "sucesso")
    return redirect(url_for("comunidade.detalhe", id=id))


def _votar(alvo_tipo, alvo_obj, redirect_endpoint, redirect_kwargs):
    # Volta para onde o voto foi disparado (feed ou detalhe) em vez de forçar
    # sempre a navegação para a página do post — melhor UX ao votar a partir
    # do feed, onde só se quer atualizar o número, não sair da lista.
    destino = request.referrer or url_for(redirect_endpoint, **redirect_kwargs)

    if current_user.id == alvo_obj.autor_id:
        flash("Não podes votar no teu próprio conteúdo.", "aviso")
        return redirect(destino)

    valor = request.form.get("valor", type=int)
    if valor not in (1, -1):
        flash("Voto inválido.", "erro")
        return redirect(destino)

    aplicar_voto(current_user, alvo_tipo, alvo_obj.id, alvo_obj, valor)
    db.session.commit()
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
    db.session.delete(resposta)
    db.session.commit()
    flash("Resposta eliminada.", "aviso")
    return redirect(url_for("comunidade.detalhe", id=post_id))
