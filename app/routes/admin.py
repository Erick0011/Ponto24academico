from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria
from app.models.user import User
from app.services.creditos_service import dar_creditos_upload
from app.services.upload_service import apagar_ficheiro

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator que restringe acesso a administradores."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@login_required
@admin_required
def painel():
    """Painel de administração."""
    pendentes = Material.query.filter_by(status=Material.STATUS_PENDENTE).count()
    total_users = User.query.count()
    total_materiais = Material.query.filter_by(status=Material.STATUS_APROVADO).count()
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


@admin_bp.route("/moderacao")
@login_required
@admin_required
def moderacao():
    """Lista materiais pendentes de aprovação."""
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
@admin_required
def aprovar(id):
    material = Material.query.get_or_404(id)
    material.status = Material.STATUS_APROVADO
    material.moderado_por_id = current_user.id
    db.session.commit()

    # Recompensa o autor
    dar_creditos_upload(material.autor)

    flash(f"Material '{material.titulo}' aprovado. Autor recebeu créditos.", "sucesso")
    return redirect(url_for("admin.moderacao"))


@admin_bp.route("/materiais/<int:id>/rejeitar", methods=["POST"])
@login_required
@admin_required
def rejeitar(id):
    material = Material.query.get_or_404(id)
    motivo = request.form.get("motivo", "").strip()

    material.status = Material.STATUS_REJEITADO
    material.motivo_rejeicao = motivo
    material.moderado_por_id = current_user.id
    db.session.commit()

    flash(f"Material '{material.titulo}' rejeitado.", "aviso")
    return redirect(url_for("admin.moderacao"))


@admin_bp.route("/utilizadores")
@login_required
@admin_required
def utilizadores():
    """Lista todos os utilizadores."""
    page = request.args.get("page", 1, type=int)
    users = User.query.order_by(User.criado_em.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/utilizadores.html", users=users)


# --- Gestão de Categorias ---

@admin_bp.route("/materiais/<int:id>/rever")
@login_required
@admin_required
def rever_material(id):
    """Página de revisão detalhada de um material (com preview do ficheiro)."""
    material = Material.query.get_or_404(id)

    pendentes = (
        Material.query
        .filter_by(status=Material.STATUS_PENDENTE)
        .order_by(Material.criado_em.asc())
        .with_entities(Material.id)
        .all()
    )
    pendentes_ids = [r[0] for r in pendentes]

    idx = pendentes_ids.index(id) if id in pendentes_ids else -1
    prev_id = pendentes_ids[idx - 1] if idx > 0 else None
    next_id = pendentes_ids[idx + 1] if 0 <= idx < len(pendentes_ids) - 1 else None
    total = len(pendentes_ids)
    pos = idx + 1 if idx >= 0 else 0

    return render_template(
        "admin/rever.html",
        material=material,
        prev_id=prev_id,
        next_id=next_id,
        total=total,
        pos=pos,
    )


@admin_bp.route("/materiais")
@login_required
@admin_required
def todos_materiais():
    """Lista todos os materiais com filtros por status e pesquisa."""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()

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
        "todos": Material.query.count(),
        "pendente": Material.query.filter_by(status=Material.STATUS_PENDENTE).count(),
        "aprovado": Material.query.filter_by(status=Material.STATUS_APROVADO).count(),
        "rejeitado": Material.query.filter_by(status=Material.STATUS_REJEITADO).count(),
    }

    return render_template(
        "admin/todos_materiais.html",
        materiais=materiais,
        counts=counts,
        status=status,
        q=q,
    )


@admin_bp.route("/materiais/<int:id>/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_material(id):
    """Elimina permanentemente um material e o seu ficheiro."""
    material = Material.query.get_or_404(id)
    titulo = material.titulo
    apagar_ficheiro(material.ficheiro_path)
    db.session.delete(material)
    db.session.commit()
    flash(f"Material '{titulo}' eliminado.", "aviso")
    return redirect(request.referrer or url_for("admin.todos_materiais"))


@admin_bp.route("/utilizadores/<int:id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(id):
    """Promove ou remove privilégios de administrador."""
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("Não podes alterar os teus próprios privilégios.", "aviso")
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        estado = "promovido a admin" if user.is_admin else "removido de admin"
        flash(f"{user.nome} {estado}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


@admin_bp.route("/utilizadores/<int:id>/toggle-ativo", methods=["POST"])
@login_required
@admin_required
def toggle_ativo(id):
    """Ativa ou desativa uma conta de utilizador."""
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
    """Adiciona ou remove créditos de um utilizador."""
    user = User.query.get_or_404(id)
    quantidade = request.form.get("quantidade", type=int)
    if quantidade is None:
        flash("Quantidade inválida.", "erro")
    else:
        user.creditos = max(0, user.creditos + quantidade)
        db.session.commit()
        sinal = "+" if quantidade >= 0 else ""
        flash(f"{user.nome}: {sinal}{quantidade} créditos. Saldo atual: {user.creditos}.", "sucesso")
    return redirect(url_for("admin.utilizadores"))


@admin_bp.route("/categorias", methods=["GET", "POST"])
@login_required
@admin_required
def categorias():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        icone = request.form.get("icone", "📄").strip()
        descricao = request.form.get("descricao", "").strip()

        if not nome:
            flash("Nome da categoria é obrigatório.", "erro")
        elif Categoria.query.filter_by(nome=nome).first():
            flash("Já existe uma categoria com esse nome.", "erro")
        else:
            db.session.add(Categoria(nome=nome, icone=icone, descricao=descricao))
            db.session.commit()
            flash(f"Categoria '{nome}' criada.", "sucesso")

    todas = Categoria.query.all()
    return render_template("admin/categorias.html", categorias=todas)
