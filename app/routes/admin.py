from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria
from app.models.user import User
from app.models.kpi import PesquisaLog
from app.models.configuracao import Configuracao
from app.models.lista_espera import ListaEspera, RelatorioMaterial
from app.models.anuncio import Anuncio
from app.services.creditos_service import dar_creditos_upload
from app.services.upload_service import apagar_ficheiro
from app.services.notificacoes_service import notificar_aprovacao, notificar_rejeicao
from app.services.mail_service import email_material_aprovado, email_material_rejeitado, email_convite_acesso
from app.services.tokens_service import gerar_token, SALT_CONVITE

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Só administradores."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def moderador_required(f):
    """Administradores ou moderadores."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or (
            not current_user.is_admin and not current_user.is_moderador
        ):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Painel ────────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
@moderador_required
def painel():
    pendentes        = Material.query.filter_by(status=Material.STATUS_PENDENTE).count()
    total_users      = User.query.count()
    total_materiais  = Material.query.filter_by(status=Material.STATUS_APROVADO).count()
    total_rejeitados = Material.query.filter_by(status=Material.STATUS_REJEITADO).count()
    total_categorias = Categoria.query.count()
    total_espera     = ListaEspera.query.filter_by(status=ListaEspera.STATUS_PENDENTE).count()
    total_relatorios = RelatorioMaterial.query.filter_by(status=RelatorioMaterial.STATUS_PENDENTE).count()

    return render_template(
        "admin/painel.html",
        pendentes=pendentes,
        total_users=total_users,
        total_materiais=total_materiais,
        total_rejeitados=total_rejeitados,
        total_categorias=total_categorias,
        total_espera=total_espera,
        total_relatorios=total_relatorios,
    )


# ── KPI (só admin) ────────────────────────────────────────────────────────────

@admin_bp.route("/kpi")
@login_required
@admin_required
def kpi():
    hoje   = datetime.utcnow()
    h30    = hoje - timedelta(days=30)
    h7     = hoje - timedelta(days=7)

    # ── Pesquisas ──────────────────────────────────────────────────────────
    total_pesquisas = PesquisaLog.query.filter(PesquisaLog.criado_em >= h30).count()

    top_termos = (
        db.session.query(PesquisaLog.termo, func.count(PesquisaLog.id).label("n"))
        .filter(PesquisaLog.criado_em >= h30)
        .group_by(PesquisaLog.termo)
        .order_by(func.count(PesquisaLog.id).desc())
        .limit(20).all()
    )

    sem_resultados = (
        db.session.query(PesquisaLog.termo, func.count(PesquisaLog.id).label("n"))
        .filter(PesquisaLog.n_resultados == 0, PesquisaLog.criado_em >= h30)
        .group_by(PesquisaLog.termo)
        .order_by(func.count(PesquisaLog.id).desc())
        .limit(20).all()
    )

    # ── Materiais ──────────────────────────────────────────────────────────
    top_downloads = (
        Material.query
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.downloads.desc())
        .limit(10).all()
    )

    por_categoria = (
        db.session.query(Categoria.nome, func.count(Material.id).label("n"))
        .join(Material, Material.categoria_id == Categoria.id)
        .filter(Material.status == Material.STATUS_APROVADO)
        .group_by(Categoria.nome)
        .order_by(func.count(Material.id).desc())
        .all()
    )

    novos_materiais_semana = (
        Material.query
        .filter(Material.criado_em >= h7, Material.status == Material.STATUS_APROVADO)
        .count()
    )

    # ── Utilizadores ──────────────────────────────────────────────────────
    novos_users_semana = User.query.filter(User.criado_em >= h7).count()
    novos_users_mes    = User.query.filter(User.criado_em >= h30).count()

    return render_template(
        "admin/kpi.html",
        total_pesquisas=total_pesquisas,
        top_termos=top_termos,
        sem_resultados=sem_resultados,
        top_downloads=top_downloads,
        por_categoria=por_categoria,
        novos_materiais_semana=novos_materiais_semana,
        novos_users_semana=novos_users_semana,
        novos_users_mes=novos_users_mes,
        total_users=User.query.count(),
        total_materiais=Material.query.filter_by(status=Material.STATUS_APROVADO).count(),
    )


# ── Moderação ─────────────────────────────────────────────────────────────────

@admin_bp.route("/moderacao")
@login_required
@moderador_required
def moderacao():
    page = request.args.get("page", 1, type=int)
    materiais = (
        Material.query
        .filter_by(status=Material.STATUS_PENDENTE)
        .order_by(Material.criado_em.asc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("admin/moderacao.html", materiais=materiais)


@admin_bp.route("/materiais/<int:id>/aprovar", methods=["POST"])
@login_required
@moderador_required
def aprovar(id):
    material = Material.query.get_or_404(id)
    material.status = Material.STATUS_APROVADO
    material.moderado_por_id = current_user.id

    dar_creditos_upload(material.autor)
    notificar_aprovacao(material)
    db.session.commit()
    email_material_aprovado(material)

    flash(f"Material '{material.titulo_base}' aprovado.", "sucesso")
    next_url = request.form.get("next_url") or url_for("admin.moderacao")
    return redirect(next_url)


@admin_bp.route("/materiais/<int:id>/rejeitar", methods=["POST"])
@login_required
@moderador_required
def rejeitar(id):
    material = Material.query.get_or_404(id)
    motivo   = request.form.get("motivo", "").strip()

    material.status = Material.STATUS_REJEITADO
    material.motivo_rejeicao = motivo
    material.moderado_por_id = current_user.id

    notificar_rejeicao(material, motivo)
    db.session.commit()
    email_material_rejeitado(material, motivo)

    flash(f"Material '{material.titulo_base}' rejeitado.", "aviso")
    next_url = request.form.get("next_url") or url_for("admin.moderacao")
    return redirect(next_url)


@admin_bp.route("/materiais/<int:id>/rever")
@login_required
@moderador_required
def rever_material(id):
    material = Material.query.get_or_404(id)

    pendentes = (
        Material.query
        .filter_by(status=Material.STATUS_PENDENTE)
        .order_by(Material.criado_em.asc())
        .with_entities(Material.id)
        .all()
    )
    pendentes_ids = [r[0] for r in pendentes]

    idx     = pendentes_ids.index(id) if id in pendentes_ids else -1
    prev_id = pendentes_ids[idx - 1] if idx > 0 else None
    next_id = pendentes_ids[idx + 1] if 0 <= idx < len(pendentes_ids) - 1 else None
    total   = len(pendentes_ids)
    pos     = idx + 1 if idx >= 0 else 0

    similares = (
        Material.query
        .filter(
            Material.status == Material.STATUS_APROVADO,
            Material.id != material.id,
            Material.disciplina.ilike(f"%{material.disciplina}%"),
            db.or_(
                Material.instituicao.ilike(f"%{material.instituicao}%"),
                Material.categoria_id == material.categoria_id,
                Material.ano_letivo == material.ano_letivo,
            ),
        )
        .order_by(Material.criado_em.desc())
        .limit(6).all()
    )

    return render_template(
        "admin/rever.html",
        material=material,
        prev_id=prev_id,
        next_id=next_id,
        total=total,
        pos=pos,
        similares=similares,
    )


# ── Gestão de materiais (só admin) ────────────────────────────────────────────

@admin_bp.route("/materiais")
@login_required
@admin_required
def todos_materiais():
    page   = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    q      = request.args.get("q", "").strip()

    query = Material.query
    if status:
        query = query.filter_by(status=status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Material.titulo.ilike(like), Material.disciplina.ilike(like))
        )

    materiais = query.order_by(Material.criado_em.desc()).paginate(page=page, per_page=25, error_out=False)

    counts = {
        "todos":     Material.query.count(),
        "pendente":  Material.query.filter_by(status=Material.STATUS_PENDENTE).count(),
        "aprovado":  Material.query.filter_by(status=Material.STATUS_APROVADO).count(),
        "rejeitado": Material.query.filter_by(status=Material.STATUS_REJEITADO).count(),
    }

    return render_template(
        "admin/todos_materiais.html",
        materiais=materiais, counts=counts, status=status, q=q,
    )


@admin_bp.route("/materiais/<int:id>/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_material(id):
    material = Material.query.get_or_404(id)
    titulo   = material.titulo
    apagar_ficheiro(material.ficheiro_path)
    db.session.delete(material)
    db.session.commit()
    flash(f"Material '{titulo}' eliminado.", "aviso")
    return redirect(request.referrer or url_for("admin.todos_materiais"))


# ── Gestão de utilizadores (só admin) ─────────────────────────────────────────

@admin_bp.route("/utilizadores")
@login_required
@admin_required
def utilizadores():
    page  = request.args.get("page", 1, type=int)
    users = User.query.order_by(User.criado_em.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/utilizadores.html", users=users)


@admin_bp.route("/utilizadores/<int:id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Não podes alterar os teus próprios privilégios.", "aviso")
    else:
        user.is_admin = not user.is_admin
        if user.is_admin:
            user.is_moderador = False  # admin > moderador
        db.session.commit()
        estado = "promovido a admin" if user.is_admin else "removido de admin"
        flash(f"{user.nome} {estado}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


@admin_bp.route("/utilizadores/<int:id>/toggle-moderador", methods=["POST"])
@login_required
@admin_required
def toggle_moderador(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash("Admins já têm permissões de moderação.", "aviso")
    else:
        user.is_moderador = not user.is_moderador
        db.session.commit()
        estado = "promovido a moderador" if user.is_moderador else "removido de moderador"
        flash(f"{user.nome} {estado}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


@admin_bp.route("/utilizadores/<int:id>/toggle-ativo", methods=["POST"])
@login_required
@admin_required
def toggle_ativo(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Não podes desativar a tua própria conta.", "aviso")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        estado = "ativada" if user.is_active else "desativada"
        flash(f"Conta de {user.nome} {estado}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


@admin_bp.route("/utilizadores/<int:id>/creditos", methods=["POST"])
@login_required
@admin_required
def ajustar_creditos(id):
    user      = User.query.get_or_404(id)
    quantidade = request.form.get("quantidade", type=int)
    if quantidade is None:
        flash("Quantidade inválida.", "erro")
    else:
        user.creditos = max(0, user.creditos + quantidade)
        db.session.commit()
        sinal = "+" if quantidade >= 0 else ""
        flash(f"{user.nome}: {sinal}{quantidade} créditos. Saldo: {user.creditos}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


# ── Categorias (só admin) ─────────────────────────────────────────────────────

@admin_bp.route("/categorias", methods=["GET", "POST"])
@login_required
@admin_required
def categorias():
    if request.method == "POST":
        cat_id    = request.form.get("id", "").strip()
        nome      = request.form.get("nome", "").strip()
        icone     = request.form.get("icone", "bi-file-earmark").strip() or "bi-file-earmark"
        descricao = request.form.get("descricao", "").strip()

        if not nome:
            flash("Nome da categoria é obrigatório.", "erro")
        elif cat_id:
            # Editar existente
            cat = Categoria.query.get_or_404(int(cat_id))
            cat.nome = nome
            cat.icone = icone
            cat.descricao = descricao
            db.session.commit()
            flash(f"Categoria '{nome}' atualizada.", "sucesso")
        elif Categoria.query.filter_by(nome=nome).first():
            flash("Já existe uma categoria com esse nome.", "erro")
        else:
            db.session.add(Categoria(nome=nome, icone=icone, descricao=descricao))
            db.session.commit()
            flash(f"Categoria '{nome}' criada.", "sucesso")

    todas = Categoria.query.all()
    return render_template("admin/categorias.html", categorias=todas)


@admin_bp.route("/categorias/<int:id>/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_categoria(id):
    cat = Categoria.query.get_or_404(id)
    if cat.materiais.count() > 0:
        flash("Não é possível eliminar uma categoria com materiais associados.", "erro")
    else:
        nome = cat.nome
        db.session.delete(cat)
        db.session.commit()
        flash(f"Categoria '{nome}' eliminada.", "aviso")
    return redirect(url_for("admin.categorias"))


# ── Configurações da plataforma (só admin) ────────────────────────────────────

@admin_bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
@admin_required
def configuracoes():
    if request.method == "POST":
        campos = [
            "email_suporte", "whatsapp", "instagram", "telegram",
            "facebook", "endereco", "texto_suporte",
            "modo_pre_lancamento",
        ]
        for campo in campos:
            Configuracao.set(campo, request.form.get(campo, "").strip())
        db.session.commit()
        flash("Configurações guardadas com sucesso.", "sucesso")
        return redirect(url_for("admin.configuracoes"))

    from app.models.lista_espera import ListaEspera as LE
    cfg = Configuracao.get_all_dict()
    stats = {
        "espera":    LE.query.filter_by(status=LE.STATUS_PENDENTE).count(),
        "pendentes": Material.query.filter_by(status=Material.STATUS_PENDENTE).count(),
        "users":     User.query.count(),
    }
    return render_template("admin/configuracoes.html", cfg=cfg, stats=stats)


# ── Lista de espera / Acesso antecipado (só admin) ────────────────────────────

@admin_bp.route("/lista-espera")
@login_required
@admin_required
def lista_espera():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = ListaEspera.query
    if status:
        query = query.filter_by(status=status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(ListaEspera.email.ilike(like), ListaEspera.nome.ilike(like),
                   ListaEspera.instituicao.ilike(like))
        )
    entradas = query.order_by(ListaEspera.criado_em.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    counts = {
        "todos":     ListaEspera.query.count(),
        "pendente":  ListaEspera.query.filter_by(status=ListaEspera.STATUS_PENDENTE).count(),
        "convidado": ListaEspera.query.filter_by(status=ListaEspera.STATUS_CONVIDADO).count(),
        "registado": ListaEspera.query.filter_by(status=ListaEspera.STATUS_REGISTADO).count(),
    }

    return render_template(
        "admin/lista_espera.html",
        entradas=entradas, counts=counts, status=status, q=q,
    )


@admin_bp.route("/lista-espera/<int:id>/convidar", methods=["POST"])
@login_required
@admin_required
def convidar_lista_espera(id):
    entrada = ListaEspera.query.get_or_404(id)
    if entrada.status == ListaEspera.STATUS_REGISTADO:
        flash("Este utilizador já está registado.", "aviso")
        return redirect(url_for("admin.lista_espera"))

    token = gerar_token(entrada.email, SALT_CONVITE)
    url_convite = url_for("auth.registar", token=token, _external=True)

    entrada.status = ListaEspera.STATUS_CONVIDADO
    db.session.commit()

    email_convite_acesso(entrada, url_convite)
    flash(f"Convite enviado para {entrada.email}.", "sucesso")
    return redirect(url_for("admin.lista_espera"))


@admin_bp.route("/lista-espera/<int:id>/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_lista_espera(id):
    entrada = ListaEspera.query.get_or_404(id)
    db.session.delete(entrada)
    db.session.commit()
    flash("Entrada removida da lista.", "aviso")
    return redirect(url_for("admin.lista_espera"))


# ── Relatórios de materiais (moderadores e admins) ────────────────────────────

@admin_bp.route("/relatorios")
@login_required
@moderador_required
def relatorios():
    status = request.args.get("status", "pendente")
    page = request.args.get("page", 1, type=int)

    query = RelatorioMaterial.query
    if status and status != "todos":
        query = query.filter_by(status=status)

    relatorios_pag = query.order_by(RelatorioMaterial.criado_em.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    counts = {
        "todos":     RelatorioMaterial.query.count(),
        "pendente":  RelatorioMaterial.query.filter_by(status=RelatorioMaterial.STATUS_PENDENTE).count(),
        "resolvido": RelatorioMaterial.query.filter_by(status=RelatorioMaterial.STATUS_RESOLVIDO).count(),
        "ignorado":  RelatorioMaterial.query.filter_by(status=RelatorioMaterial.STATUS_IGNORADO).count(),
    }

    return render_template(
        "admin/relatorios.html",
        relatorios=relatorios_pag, counts=counts, status=status,
    )


@admin_bp.route("/relatorios/<int:id>/resolver", methods=["POST"])
@login_required
@moderador_required
def resolver_relatorio(id):
    relatorio = RelatorioMaterial.query.get_or_404(id)
    acao = request.form.get("acao", "resolvido")
    relatorio.status = acao
    db.session.commit()
    flash("Relatório atualizado.", "sucesso")
    return redirect(request.referrer or url_for("admin.relatorios"))


# ── Logs da aplicação ─────────────────────────────────────────────────────────

@admin_bp.route("/logs")
@login_required
@admin_required
def logs():
    import os as _os
    nivel = request.args.get("nivel", "")
    log_path = _os.path.join(current_app.root_path, "..", "logs", "ponto24.log")
    linhas = []
    if _os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            todas = f.readlines()
        if nivel:
            todas = [l for l in todas if f" {nivel.upper()} " in l or f" {nivel.upper()}\t" in l]
        linhas = list(reversed(todas[-1000:]))
    return render_template("admin/logs.html", linhas=linhas, nivel=nivel)


# ── Anúncios ──────────────────────────────────────────────────────────────────

@admin_bp.route("/anuncios")
@login_required
@admin_required
def anuncios():
    todos = Anuncio.query.order_by(Anuncio.data_inicio.desc()).all()
    disponivel = Anuncio.percentagem_disponivel()
    return render_template("admin/anuncios.html", anuncios=todos, disponivel=disponivel)


def _guardar_banner(ficheiro):
    """Guarda imagem de banner em R2 ou local. Devolve (banner_key, banner_url)."""
    import uuid, os
    ext = ficheiro.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        return None, None
    dados = ficheiro.read()
    key = f"anuncios/{uuid.uuid4().hex}.{ext}"
    if os.environ.get("R2_ENDPOINT"):
        from app.services.r2_service import upload_bytes
        upload_bytes(dados, key, ext)
        return key, ""
    else:
        pasta = os.path.join(current_app.root_path, "static", "anuncios")
        os.makedirs(pasta, exist_ok=True)
        nome = key.split("/")[-1]
        with open(os.path.join(pasta, nome), "wb") as f:
            f.write(dados)
        return "", f"/static/anuncios/{nome}"


@admin_bp.route("/anuncios/criar", methods=["GET", "POST"])
@login_required
@admin_required
def criar_anuncio():
    from datetime import date as _date, timedelta
    disponivel = Anuncio.percentagem_disponivel()
    if request.method == "POST":
        anunciante   = request.form.get("anunciante", "").strip()
        contacto     = request.form.get("contacto", "").strip()
        banner_url   = request.form.get("banner_url", "").strip()
        banner_key   = ""
        link_destino = request.form.get("link_destino", "").strip()
        percentagem  = request.form.get("percentagem", type=float)
        dias         = request.form.get("dias", type=int)
        inicio_str   = request.form.get("data_inicio", "").strip()

        ficheiro = request.files.get("banner_file")
        if ficheiro and ficheiro.filename:
            bkey, burl = _guardar_banner(ficheiro)
            if bkey is None and burl is None:
                flash("Formato de imagem inválido. Usa JPG, PNG, GIF ou WEBP.", "erro")
                return render_template("admin/anuncio_form.html", anuncio=None, disponivel=disponivel)
            banner_key, banner_url = bkey, burl

        if not all([anunciante, percentagem, dias]) or (not banner_url and not banner_key):
            flash("Preenche todos os campos obrigatórios (incluindo a imagem).", "erro")
        elif percentagem > disponivel:
            flash(f"Só tens {disponivel:.0f}% disponível para vender.", "erro")
        else:
            try:
                data_inicio = _date.fromisoformat(inicio_str) if inicio_str else _date.today()
            except ValueError:
                data_inicio = _date.today()
            db.session.add(Anuncio(
                anunciante=anunciante,
                contacto=contacto,
                banner_url=banner_url,
                banner_key=banner_key,
                link_destino=link_destino,
                percentagem=percentagem,
                data_inicio=data_inicio,
                data_fim=data_inicio + timedelta(days=dias),
            ))
            db.session.commit()
            flash(f"Anúncio de {anunciante} criado com sucesso.", "sucesso")
            return redirect(url_for("admin.anuncios"))

    return render_template("admin/anuncio_form.html", anuncio=None, disponivel=disponivel)


@admin_bp.route("/anuncios/<int:id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_anuncio(id):
    anuncio = Anuncio.query.get_or_404(id)
    disponivel = Anuncio.percentagem_disponivel() + anuncio.percentagem
    if request.method == "POST":
        from datetime import date as _date, timedelta
        anuncio.anunciante   = request.form.get("anunciante", "").strip()
        anuncio.contacto     = request.form.get("contacto", "").strip()
        anuncio.link_destino = request.form.get("link_destino", "").strip()
        anuncio.percentagem  = request.form.get("percentagem", type=float)
        anuncio.ativo        = request.form.get("ativo") == "1"

        ficheiro = request.files.get("banner_file")
        if ficheiro and ficheiro.filename:
            bkey, burl = _guardar_banner(ficheiro)
            if bkey is None and burl is None:
                flash("Formato de imagem inválido.", "erro")
                return render_template("admin/anuncio_form.html", anuncio=anuncio, disponivel=disponivel)
            # apagar banner antigo do R2
            if anuncio.banner_key:
                import os
                if os.environ.get("R2_ENDPOINT"):
                    from app.services.r2_service import delete_object
                    delete_object(anuncio.banner_key)
            anuncio.banner_key = bkey
            anuncio.banner_url = burl
        else:
            url_manual = request.form.get("banner_url", "").strip()
            if url_manual:
                anuncio.banner_url = url_manual
                anuncio.banner_key = ""

        dias = request.form.get("dias", type=int)
        inicio_str = request.form.get("data_inicio", "").strip()
        try:
            anuncio.data_inicio = _date.fromisoformat(inicio_str)
        except ValueError:
            pass
        if dias:
            anuncio.data_fim = anuncio.data_inicio + timedelta(days=dias)
        db.session.commit()
        flash("Anúncio actualizado.", "sucesso")
        return redirect(url_for("admin.anuncios"))
    return render_template("admin/anuncio_form.html", anuncio=anuncio, disponivel=disponivel)


@admin_bp.route("/anuncios/<int:id>/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_anuncio(id):
    import os
    anuncio = Anuncio.query.get_or_404(id)
    if anuncio.banner_key and os.environ.get("R2_ENDPOINT"):
        from app.services.r2_service import delete_object
        delete_object(anuncio.banner_key)
    db.session.delete(anuncio)
    db.session.commit()
    flash("Anúncio eliminado.", "aviso")
    return redirect(url_for("admin.anuncios"))
