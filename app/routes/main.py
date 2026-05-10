import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page / home."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Estatísticas públicas
    total_materiais = Material.query.filter_by(status=Material.STATUS_APROVADO).count()
    categorias = Categoria.query.all()
    recentes = (
        Material.query
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "index.html",
        total_materiais=total_materiais,
        categorias=categorias,
        recentes=recentes,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Dashboard do utilizador autenticado."""
    meus_materiais = (
        current_user.materiais
        .order_by(Material.criado_em.desc())
        .limit(5)
        .all()
    )
    recentes = (
        Material.query
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(6)
        .all()
    )
    populares = (
        Material.query
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.downloads.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        meus_materiais=meus_materiais,
        recentes=recentes,
        populares=populares,
    )


@main_bp.route("/perfil")
@login_required
def perfil():
    """Perfil do utilizador atual."""
    materiais_aprovados = (
        current_user.materiais
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .all()
    )
    return render_template("dashboard/perfil.html", materiais=materiais_aprovados)


@main_bp.route("/como-funciona")
def como_funciona():
    return render_template("main/como_funciona.html")


@main_bp.route("/provas-simuladas")
def provas_simuladas():
    universidade = request.args.get("universidade", "").strip()
    disciplina = request.args.get("disciplina", "").strip()
    tipo = request.args.get("tipo", "").strip()
    ano = request.args.get("ano", "").strip()

    materiais = []
    if any([universidade, disciplina, tipo, ano]):
        query = Material.query.filter_by(status=Material.STATUS_APROVADO)
        if universidade:
            query = query.filter(Material.instituicao.ilike(f"%{universidade}%"))
        if disciplina:
            query = query.filter(Material.disciplina.ilike(f"%{disciplina}%"))
        if tipo:
            query = query.filter(Material.semestre == tipo)
        if ano:
            query = query.filter(Material.ano_letivo == ano)
        materiais = query.order_by(Material.criado_em.desc()).limit(60).all()

    return render_template(
        "main/provas_simuladas.html",
        materiais=materiais,
        filtros={"universidade": universidade, "disciplina": disciplina, "tipo": tipo, "ano": ano},
    )


@main_bp.route("/perfil/editar", methods=["POST"])
@login_required
def editar_perfil():
    """Atualiza dados do perfil."""
    current_user.nome = request.form.get("nome", current_user.nome).strip()
    current_user.instituicao = request.form.get("instituicao", "").strip()
    current_user.curso = request.form.get("curso", "").strip()
    current_user.bio = request.form.get("bio", "").strip()
    db.session.commit()
    flash("Perfil atualizado!", "sucesso")
    return redirect(url_for("main.perfil"))
