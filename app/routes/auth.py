from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.services.creditos_service import creditos_ao_registar
from app.services.mail_service import email_boas_vindas

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/registar", methods=["GET", "POST"])
def registar():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmacao = request.form.get("confirmacao", "")
        instituicao = request.form.get("instituicao", "").strip()
        curso = request.form.get("curso", "").strip()

        # Validações básicas
        if not nome or not email or not password:
            flash("Preenche todos os campos obrigatórios.", "erro")
            return render_template("auth/registar.html")

        if password != confirmacao:
            flash("As palavras-passe não coincidem.", "erro")
            return render_template("auth/registar.html")

        if len(password) < 6:
            flash("A palavra-passe deve ter pelo menos 6 caracteres.", "erro")
            return render_template("auth/registar.html")

        if User.query.filter_by(email=email).first():
            flash("Este email já está registado.", "erro")
            return render_template("auth/registar.html")

        # Criar utilizador
        user = User(
            nome=nome,
            email=email,
            instituicao=instituicao,
            curso=curso,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()          # Obter o ID antes do commit
        creditos_ao_registar(user)  # Dá créditos iniciais
        db.session.commit()

        login_user(user)
        email_boas_vindas(user)
        flash(f"Bem-vindo(a), {user.nome}! Tens {user.creditos} créditos de boas-vindas.", "sucesso")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/registar.html")


@auth_bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        lembrar = request.form.get("lembrar") == "on"

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Email ou palavra-passe incorretos.", "erro")
            return render_template("auth/entrar.html")

        if not user.is_active:
            flash("Conta suspensa. Contacta o suporte.", "erro")
            return render_template("auth/entrar.html")

        login_user(user, remember=lembrar)
        flash(f"Bem-vindo(a) de volta, {user.nome}!", "sucesso")

        from urllib.parse import urlparse
        proximo = request.args.get("next", "")
        if proximo and urlparse(proximo).netloc:
            proximo = ""
        return redirect(proximo or url_for("main.dashboard"))

    return render_template("auth/entrar.html")


@auth_bp.route("/sair")
@login_required
def sair():
    logout_user()
    flash("Sessão terminada com sucesso.", "info")
    return redirect(url_for("auth.entrar"))
