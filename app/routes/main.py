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
    current_app,
)
from flask_login import login_required, current_user, logout_user
from app import db, limiter
from app.models.material import Material, Categoria, Favorito
from app.models.user import User
from app.models.configuracao import Configuracao
from app.models.lista_espera import ListaEspera
from app.models.notificacao import Notificacao
import json
from app.models import Candidatura
from app.utils.honeypot import honeypot_preenchido
from app.utils.validacao import senha_forte
from app.models.atividade import AtividadeLog
from app.services.atividade_service import registar_atividade
from app.services.tokens_service import verificar_token
from app.services.marketing_service import SALT_MARKETING_CANCELAR


def _slugify(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _truncar(texto, limite=157):
    """Corta texto no limite de caracteres sem partir palavras (para meta description)."""
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",.;") + "…"


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
    from app.services.recomendacao_service import materiais_para_utilizador

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
        recomendados=materiais_para_utilizador(current_user),
    )


@main_bp.route("/perfil")
@login_required
def perfil():
    """Perfil do utilizador atual."""
    from app.services.badges_service import badges_do_utilizador

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
        badges=badges_do_utilizador(current_user),
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
    from app.services.badges_service import badges_do_utilizador

    autor = User.query.get_or_404(id)
    materiais = (
        autor.materiais.filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .all()
    )
    total_downloads = sum(m.downloads for m in materiais)
    partes = [autor.nome]
    if autor.instituicao:
        partes.append(autor.instituicao)
    meta_descricao = _truncar(
        f"{' — '.join(partes)}. {len(materiais)} materiais partilhados no Ponto 24 Académico."
    )
    return render_template(
        "main/perfil_publico.html",
        autor=autor,
        materiais=materiais,
        total_downloads=total_downloads,
        meta_descricao=meta_descricao,
        badges=badges_do_utilizador(autor),
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


@main_bp.route("/definicoes")
@login_required
def definicoes():
    """Definições da conta: preferências e eliminação de conta (compliance —
    ver política de privacidade §5/§6)."""
    return render_template("dashboard/definicoes.html")


@main_bp.route("/definicoes/marketing", methods=["POST"])
@login_required
def alternar_marketing():
    current_user.aceita_marketing = not current_user.aceita_marketing
    if not current_user.aceita_marketing:
        registar_atividade(AtividadeLog.EVENTO_MARKETING_CANCELADO, utilizador_id=current_user.id)
    db.session.commit()
    flash(
        "Vais continuar a receber emails de marketing." if current_user.aceita_marketing
        else "Já não vais receber emails de marketing.",
        "sucesso",
    )
    return redirect(url_for("main.definicoes"))


@main_bp.route("/definicoes/eliminar-conta", methods=["POST"])
@login_required
@limiter.limit("5 per hour", methods=["POST"])
def eliminar_conta():
    """Eliminação de conta a pedido do próprio. Exige a senha atual — ação
    irreversível — e anonimiza em vez de apagar a linha (ver User.anonimizar),
    para não partir materiais/posts/avaliações já publicados por este
    utilizador nem os FKs de outras tabelas que apontam para o seu id."""
    senha = request.form.get("senha", "")
    confirmacao = request.form.get("confirmacao", "").strip().upper()

    if not current_user.check_password(senha):
        flash("Senha incorreta. A conta não foi eliminada.", "erro")
        return redirect(url_for("main.definicoes"))
    if confirmacao != "ELIMINAR":
        flash('Escreve "ELIMINAR" para confirmar. A conta não foi eliminada.', "erro")
        return redirect(url_for("main.definicoes"))

    uid = current_user.id
    # Dados só relevantes para o próprio — sem valor para outros utilizadores
    # nem para o histórico da plataforma — são apagados por completo.
    Favorito.query.filter_by(utilizador_id=uid).delete()
    Notificacao.query.filter_by(utilizador_id=uid).delete()

    current_user.anonimizar()
    registar_atividade(AtividadeLog.EVENTO_CONTA_ELIMINADA, utilizador_id=uid)
    db.session.commit()

    logout_user()
    flash("A tua conta e os teus dados pessoais foram eliminados.", "sucesso")
    return redirect(url_for("main.index"))


@main_bp.route("/sobre")
def sobre_nos():
    secao = request.args.get("secao", "sobre")
    if secao not in ("sobre", "visao", "missao"):
        secao = "sobre"
    titulos = {"sobre": "Sobre Nós", "visao": "Visão", "missao": "Missão"}
    return render_template("main/sobre.html", secao=secao, titulo=titulos[secao])


@main_bp.route("/termos")
def termos():
    return render_template("main/termos.html")


@main_bp.route("/privacidade")
def privacidade():
    return render_template("main/privacidade.html")


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


def _stats_candidatura():
    """Números para a secção de prova social da página de candidatura."""
    total_candidaturas = Candidatura.query.count()
    total_universidades = (
        db.session.query(Candidatura.universidade)
        .filter(Candidatura.universidade.isnot(None), Candidatura.universidade != "")
        .distinct()
        .count()
    )
    return {
        "total_candidaturas": total_candidaturas,
        "total_universidades": total_universidades,
    }


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
            return render_template("main/juntar_se.html", **_stats_candidatura()), 400

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
            db.session.flush()
            registar_atividade(
                AtividadeLog.EVENTO_CANDIDATURA_RECEBIDA,
                utilizador_id=current_user.id if current_user.is_authenticated else None,
                alvo_tipo="candidatura", alvo_id=nova.id,
                detalhes={"nome": nome, "email": email},
            )
            db.session.commit()

            flash(
                "Candidatura enviada com sucesso! Entraremos em contacto em breve.",
                "success",
            )
            return redirect(url_for("main.juntar_se"))

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao guardar candidatura")
            flash(
                "Ocorreu um erro ao guardar a candidatura. Tenta novamente.", "danger"
            )
            return render_template("main/juntar_se.html", **_stats_candidatura()), 500

    # GET
    return render_template("main/juntar_se.html", **_stats_candidatura())


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
            entrada = ListaEspera(
                nome=nome,
                email=email,
                instituicao=instituicao,
                mensagem=mensagem,
            )
            db.session.add(entrada)
            db.session.flush()
            registar_atividade(
                AtividadeLog.EVENTO_LISTA_ESPERA,
                utilizador_id=None, alvo_tipo="lista_espera", alvo_id=entrada.id,
                detalhes={"nome": nome, "email": email},
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
        "Disallow: /dashboard",
        "Disallow: /perfil",
        "Disallow: /materiais/submeter",
        "Disallow: /materiais/*/preview",
        "Disallow: /materiais/*/download",
        "Disallow: /marketing/cancelar/",
        "",
        f"Sitemap: {url_for('main.sitemap_xml', _external=True)}",
    ]
    return Response("\n".join(linhas), mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    """Sitemap gerado dinamicamente a partir dos dados — nunca escrito à mão,
    para não desatualizar à medida que materiais, pastas e perfis mudam.
    Só inclui páginas públicas e efetivamente indexáveis (200, sem noindex,
    sem exigir login)."""
    now = datetime.utcnow().strftime("%Y-%m-%d")
    urls = [
        # (loc, lastmod, changefreq, priority)
        (url_for("main.index", _external=True), now, "daily", "1.0"),
        (url_for("materiais.listar", _external=True), now, "daily", "0.9"),
        (url_for("materiais.pastas_raiz", _external=True), now, "weekly", "0.6"),
        (url_for("main.como_funciona", _external=True), now, "monthly", "0.6"),
        (url_for("main.sobre_nos", _external=True), now, "monthly", "0.5"),
        (url_for("main.anunciar", _external=True), now, "monthly", "0.4"),
        (url_for("main.suporte", _external=True), now, "yearly", "0.3"),
        (url_for("main.juntar_se", _external=True), now, "monthly", "0.3"),
        # Nota: "/provas-simuladas" fica de fora — página "em construção",
        # sem conteúdo real ainda (ver meta_robots noindex no próprio template).
    ]

    materiais = (
        Material.query.filter_by(status=Material.STATUS_APROVADO)
        .order_by(Material.criado_em.desc())
        .limit(2000)
        .all()
    )
    urls += [
        (
            url_for("materiais.detalhe", id=m.id, _external=True),
            (m.atualizado_em or m.criado_em).strftime("%Y-%m-%d"),
            "monthly",
            "0.6",
        )
        for m in materiais
    ]

    from app.models.pasta import Pasta
    pastas = Pasta.query.order_by(Pasta.id).limit(1000).all()
    urls += [
        (
            url_for("materiais.pastas_ver", id=p.id, _external=True),
            p.criado_em.strftime("%Y-%m-%d"),
            "weekly",
            "0.5",
        )
        for p in pastas
    ]

    # Perfis públicos: só de utilizadores ativos com pelo menos 1 material
    # aprovado (evita indexar perfis vazios / sem conteúdo real).
    autores_ids = (
        db.session.query(Material.autor_id)
        .filter(Material.status == Material.STATUS_APROVADO)
        .distinct()
    )
    autores = (
        User.query.filter(User.id.in_(autores_ids), User.is_active.is_(True))
        .all()
    )
    urls += [
        (
            url_for("main.ver_perfil", id=u.id, _external=True),
            now,
            "monthly",
            "0.3",
        )
        for u in autores
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


@main_bp.route("/marketing/cancelar/<token>", methods=["GET", "POST"])
def cancelar_marketing(token):
    """Cancela a subscrição de emails de marketing. Aceita GET (link clicado
    pelo utilizador) e POST (botão "cancelar subscrição" nativo de clientes
    de email, via cabeçalho List-Unsubscribe-Post — RFC 8058)."""
    # 10 anos — link de cancelamento não deve expirar
    user_id = verificar_token(token, SALT_MARKETING_CANCELAR, max_age=60 * 60 * 24 * 3650)
    if not user_id:
        flash("Link de cancelamento inválido ou expirado.", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get(int(user_id))
    if user and user.aceita_marketing:
        user.aceita_marketing = False
        registar_atividade(
            AtividadeLog.EVENTO_MARKETING_CANCELADO,
            utilizador_id=user.id, alvo_tipo="user", alvo_id=user.id,
        )
        db.session.commit()

    return render_template("main/marketing_cancelado.html")
