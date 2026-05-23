from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria
from app.models.user import User
from app.models.kpi import PesquisaLog
from app.services.creditos_service import dar_creditos_upload
from app.services.upload_service import apagar_ficheiro
from app.services.notificacoes_service import notificar_aprovacao, notificar_rejeicao
from app.services.mail_service import email_material_aprovado, email_material_rejeitado

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

    return render_template(
        "admin/painel.html",
        pendentes=pendentes,
        total_users=total_users,
        total_materiais=total_materiais,
        total_rejeitados=total_rejeitados,
        total_categorias=total_categorias,
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
