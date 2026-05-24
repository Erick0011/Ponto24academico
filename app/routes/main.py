import os
import unicodedata
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria, Favorito
from app.models.user import User
from app.models.configuracao import Configuracao
from app.models.lista_espera import ListaEspera


def _slugify(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

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
    populares = (
        Material.query
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.downloads.desc())
        .limit(5)
        .all()
    )

    # Mapa slug → categoria_id para os cards do index
    cat_ids = {}
    for cat in categorias:
        slug = _slugify(cat.nome)
        for key in ("prova", "resumo", "exercicio", "gabarito", "apontamento"):
            if key in slug:
                cat_ids[key] = cat.id
                break

    return render_template(
        "index.html",
        total_materiais=total_materiais,
        categorias=categorias,
        recentes=recentes,
        populares=populares,
        cat_ids=cat_ids,
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
    todos_materiais = (
        current_user.materiais
        .order_by(Material.criado_em.desc())
        .all()
    )
    materiais_favoritos = [
        f.material for f in
        current_user.favoritos.order_by(Favorito.criado_em.desc()).all()
        if f.material and f.material.esta_aprovado
    ]
    return render_template(
        "dashboard/perfil.html",
        materiais=todos_materiais,
        favoritos=materiais_favoritos,
    )


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


@main_bp.route("/utilizador/<int:id>")
def ver_perfil(id):
    """Perfil público de qualquer utilizador."""
    autor = User.query.get_or_404(id)
    materiais = (
        autor.materiais
        .filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .all()
    )
    total_downloads = sum(m.downloads for m in materiais)
    return render_template(
        "main/perfil_publico.html",
        autor=autor,
        materiais=materiais,
        total_downloads=total_downloads,
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


@main_bp.route("/suporte", methods=["GET", "POST"])
def suporte():
    """Página de suporte / contacto."""
    if request.method == "POST":
        nome    = request.form.get("nome", "").strip()
        email   = request.form.get("email", "").strip()
        assunto = request.form.get("assunto", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        if not nome or not email or not mensagem:
            flash("Preenche todos os campos obrigatórios.", "erro")
        else:
            # Guarda internamente e tenta enviar por email ao suporte
            from app.services.mail_service import enviar_email
            email_suporte = Configuracao.get("email_suporte", "suporte@ponto24academico.com")
            enviar_email(
                destinatario=email_suporte,
                assunto=f"[Suporte P24] {assunto or 'Contacto do site'}",
                template_html="email/contacto_suporte.html",
                contexto={"nome": nome, "email": email, "assunto": assunto, "mensagem": mensagem},
            )
            flash("Mensagem enviada! Respondemos em 24–48 horas.", "sucesso")
            return redirect(url_for("main.suporte"))

    cfg = Configuracao.get_all_dict()
    return render_template("main/suporte.html", cfg=cfg)


@main_bp.route("/acesso-antecipado", methods=["GET", "POST"])
def acesso_antecipado():
    """Página de captação de interesse / lista de espera."""
    if request.method == "POST":
        nome        = request.form.get("nome", "").strip()
        email       = request.form.get("email", "").strip().lower()
        instituicao = request.form.get("instituicao", "").strip()
        mensagem    = request.form.get("mensagem", "").strip()

        if not email:
            flash("O email é obrigatório.", "erro")
        elif ListaEspera.query.filter_by(email=email).first():
            flash("Este email já está na lista de espera!", "aviso")
        else:
            db.session.add(ListaEspera(
                nome=nome, email=email,
                instituicao=instituicao, mensagem=mensagem,
            ))
            db.session.commit()
            flash("Estás na lista! Avisamos quando o teu acesso estiver disponível.", "sucesso")
            return redirect(url_for("main.acesso_antecipado"))

    total_espera = ListaEspera.query.count()
    return render_template("main/acesso_antecipado.html", total_espera=total_espera)


