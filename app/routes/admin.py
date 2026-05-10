from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria
from app.models.user import User
from app.services.creditos_service import dar_creditos_upload

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

    return render_template(
        "admin/painel.html",
        pendentes=pendentes,
        total_users=total_users,
        total_materiais=total_materiais,
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
