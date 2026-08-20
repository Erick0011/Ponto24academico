import unicodedata
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    Response,
)
from flask_login import login_required, current_user
from app import db, limiter
from app.models.material import Material, Categoria, Favorito
from app.models.user import User
from app.models.configuracao import Configuracao
from app.models.lista_espera import ListaEspera
import json
from app.models import Candidatura
from app.utils.honeypot import honeypot_preenchido
from app.utils.validacao import senha_forte


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
    total_instituicoes = (
        db.session.query(Material.instituicao)
        .filter(
            Material.status == Material.STATUS_APROVADO,
            Material.instituicao.isnot(None),
            Material.instituicao != "",
        )
        .distinct()
        .count()
    )
    total_disciplinas = (
        db.session.query(Material.disciplina)
        .filter(
            Material.status == Material.STATUS_APROVADO,
            Material.disciplina.isnot(None),
            Material.disciplina != "",
        )
        .distinct()
        .count()
    )
    total_estudantes = User.query.filter_by(is_active=True).count()
    categorias = Categoria.query.all()
    recentes = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(6)
        .all()
    )
    populares = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
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

    # Contagens reais de materiais aprovados por categoria (para os cards do index)
    cat_counts = {
        slug: Material.query.filter_by(
            status=Material.STATUS_APROVADO, categoria_id=cid
        ).count()
        for slug, cid in cat_ids.items()
    }

    return render_template(
        "index.html",
        total_materiais=total_materiais,
        total_instituicoes=total_instituicoes,
        total_disciplinas=total_disciplinas,
        total_estudantes=total_estudantes,
        categorias=categorias,
        recentes=recentes,
        populares=populares,
        cat_ids=cat_ids,
        cat_counts=cat_counts,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Dashboard do utilizador autenticado."""
    meus_materiais = (
        current_user.materiais.order_by(Material.criado_em.desc()).limit(5).all()
    )
    recentes = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(6)
        .all()
    )
    populares = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
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
    todos_materiais = current_user.materiais.order_by(Material.criado_em.desc()).all()
    materiais_favoritos = [
        f.material
        for f in current_user.favoritos.order_by(Favorito.criado_em.desc()).all()
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
        filtros={
            "universidade": universidade,
            "disciplina": disciplina,
            "tipo": tipo,
            "ano": ano,
        },
    )


@main_bp.route("/utilizador/<int:id>")
def ver_perfil(id):
    """Perfil público de qualquer utilizador."""
    autor = User.query.get_or_404(id)
    materiais = (
        autor.materiais.filter_by(status=Material.STATUS_APROVADO)
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


@main_bp.route("/perfil/alterar-senha", methods=["POST"])
@login_required
def alterar_senha():
    senha_atual = request.form.get("senha_atual", "")
    nova_senha = request.form.get("nova_senha", "")
    confirmar = request.form.get("confirmar_senha", "")

    if not current_user.check_password(senha_atual):
        flash("Senha atual incorreta.", "erro")
    elif not senha_forte(nova_senha):
        flash("A nova senha deve ter pelo menos 8 caracteres, com maiúscula, minúscula e número.", "erro")
    elif nova_senha != confirmar:
        flash("As senhas não coincidem.", "erro")
    else:
        current_user.set_password(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso!", "sucesso")

    return redirect(url_for("main.perfil"))


@main_bp.route("/sobre")
def sobre_nos():
    secao = request.args.get("secao", "sobre")
    if secao not in ("sobre", "visao", "missao"):
        secao = "sobre"
    titulos = {"sobre": "Sobre Nós", "visao": "Visão", "missao": "Missão"}
    return render_template("main/sobre.html", secao=secao, titulo=titulos[secao])


@main_bp.route("/suporte", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def suporte():
    """Página de suporte / contacto."""
    if request.method == "POST":
        if honeypot_preenchido():
            return redirect(url_for("main.suporte"))

        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        assunto = request.form.get("assunto", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        if not nome or not email or not mensagem:
            flash("Preenche todos os campos obrigatórios.", "erro")
        else:
            # Guarda internamente e tenta enviar por email ao suporte
            from app.services.mail_service import enviar_email

            email_suporte = Configuracao.get(
                "email_suporte", "suporte@ponto24academico.com"
            )
            enviar_email(
                destinatario=email_suporte,
                assunto=f"[Suporte P24] {assunto or 'Contacto do site'}",
                template_html="email/contacto_suporte.html",
                contexto={
                    "nome": nome,
                    "email": email,
                    "assunto": assunto,
                    "mensagem": mensagem,
                },
            )
            flash("Mensagem enviada! Respondemos em 24–48 horas.", "sucesso")
            return redirect(url_for("main.suporte"))

    cfg = Configuracao.get_all_dict()
    return render_template("main/suporte.html", cfg=cfg)


@main_bp.route("/juntar-se", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def juntar_se():
    if request.method == "POST":
        if honeypot_preenchido():
            return redirect(url_for("main.juntar_se"))

        # ── Coleta os dados ──
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefone = request.form.get("telefone", "").strip()
        universidade = request.form.get("universidade", "").strip()
        curso = request.form.get("curso", "").strip()
        ano = request.form.get("ano", "").strip()

        # Checkboxes → lista
        contribuicoes = request.form.getlist(
            "contribuicoes"
        )  # ['materiais', 'campus', ...]

        motivacao = request.form.get("motivacao", "").strip()
        impacto = request.form.get("impacto", "").strip()
        experiencia = request.form.get("experiencia", "").strip()

        lideranca = request.form.get("lideranca", "nao").strip()
        area = request.form.get("area", "").strip()
        lideranca_motivo = request.form.get("lideranca_motivo", "").strip()

        # ── Validação básica ──
        erros = []

        if not nome or len(nome) < 3:
            erros.append("O nome completo é obrigatório (mín. 3 caracteres).")

        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            erros.append("Introduz um email válido.")

        # Verifica duplicado (mesmo email)
        existente = Candidatura.query.filter_by(email=email).first()
        if existente:
            erros.append("Já existe uma candidatura com este email.")

        if erros:
            for erro in erros:
                flash(erro, "danger")
            # Volta para o formulário com os dados preenchidos (opcional)
            return render_template("main/juntar_se.html"), 400

        # ── Cria e guarda ──
        try:
            nova = Candidatura(
                nome=nome,
                email=email,
                telefone=telefone or None,
                universidade=universidade or None,
                curso=curso or None,
                ano=ano or None,
                contribuicoes=json.dumps(contribuicoes, ensure_ascii=False),
                motivacao=motivacao or None,
                impacto=impacto or None,
                experiencia=experiencia or None,
                lideranca=lideranca,
                area=area or None,
                lideranca_motivo=lideranca_motivo or None,
                status="pendente",
            )
            db.session.add(nova)
            db.session.commit()

            flash(
                "Candidatura enviada com sucesso! Entraremos em contacto em breve.",
                "success",
            )
            return redirect(url_for("main.juntar_se"))

        except Exception as e:
            db.session.rollback()
            flash(
                "Ocorreu um erro ao guardar a candidatura. Tenta novamente.", "danger"
            )
            # Em dev podes logar: app.logger.error(e)
            return render_template("main/juntar_se.html"), 500

    # GET
    return render_template("main/juntar_se.html")


@main_bp.route("/acesso-antecipado", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def acesso_antecipado():
    """Página de captação de interesse / lista de espera."""
    if request.method == "POST":
        if honeypot_preenchido():
            return redirect(url_for("main.acesso_antecipado"))

        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        instituicao = request.form.get("instituicao", "").strip()
        mensagem = request.form.get("mensagem", "").strip()

        if not email:
            flash("O email é obrigatório.", "erro")
        elif ListaEspera.query.filter_by(email=email).first():
            flash("Este email já está na lista de espera!", "aviso")
        else:
            db.session.add(
                ListaEspera(
                    nome=nome,
                    email=email,
                    instituicao=instituicao,
                    mensagem=mensagem,
                )
            )
            db.session.commit()
            flash(
                "Estás na lista! Avisamos quando o teu acesso estiver disponível.",
                "sucesso",
            )
            return redirect(url_for("main.acesso_antecipado"))

    total_espera = ListaEspera.query.count()
    return render_template("main/acesso_antecipado.html", total_espera=total_espera)


@main_bp.route("/anunciar")
def anunciar():
    from app.models.anuncio import Anuncio

    disponivel = Anuncio.percentagem_disponivel()
    return render_template("main/anunciar.html", disponivel=disponivel)


@main_bp.route("/robots.txt")
def robots_txt():
    linhas = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /auth/",
        "Disallow: /notificacoes/",
        "Disallow: /materiais/submeter",
        "",
        f"Sitemap: {url_for('main.sitemap_xml', _external=True)}",
    ]
    return Response("\n".join(linhas), mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    now = datetime.utcnow().strftime("%Y-%m-%d")
    paginas_estaticas = [
        (url_for("main.index", _external=True), now, "weekly", "1.0"),
        (url_for("main.sobre_nos", _external=True), now, "monthly", "0.8"),
        (url_for("main.como_funciona", _external=True), now, "monthly", "0.7"),
        (url_for("main.provas_simuladas", _external=True), now, "weekly", "0.8"),
        (url_for("materiais.listar", _external=True), now, "daily", "0.9"),
    ]
    materiais = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(1000)
        .all()
    )
    urls = paginas_estaticas + [
        (
            url_for("materiais.detalhe", id=m.id, _external=True),
            m.criado_em.strftime("%Y-%m-%d"),
            "monthly",
            "0.6",
        )
        for m in materiais
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for loc, lastmod, changefreq, priority in urls:
        xml.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>""")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")
