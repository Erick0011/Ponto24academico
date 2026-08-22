from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models.user import User
from app.models.lista_espera import ListaEspera
from app.services.creditos_service import creditos_ao_registar
from app.services.mail_service import (
    email_boas_vindas, email_confirmacao, email_recuperar_senha,
)
from app.services.tokens_service import (
    gerar_token, verificar_token,
    SALT_CONFIRMACAO, SALT_RECUPERACAO, SALT_CONVITE,
)
from app.utils.honeypot import honeypot_preenchido
from app.utils.validacao import senha_forte
from app.models.atividade import AtividadeLog
from app.services.atividade_service import registar_atividade

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/registar", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def registar():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    # Convite opcional (enviado a partir da Lista de Espera, em admin.lista_espera):
    # se o link for válido, pré-preenche e valida o email — mas o registo está
    # sempre aberto a qualquer pessoa, com ou sem convite.
    invite_token = request.args.get("token", "").strip()
    email_convite = verificar_token(invite_token, SALT_CONVITE, max_age=604800) if invite_token else None

    if request.method == "POST":
        if honeypot_preenchido():
            return redirect(url_for("main.index"))

        nome        = request.form.get("nome", "").strip()
        email       = request.form.get("email", "").strip().lower()
        password    = request.form.get("password", "")
        confirmacao = request.form.get("confirmacao", "")
        instituicao = request.form.get("instituicao", "").strip()
        curso       = request.form.get("curso", "").strip()

        # Se veio de um link de convite válido, o email deve coincidir com o do convite
        if email_convite and email != email_convite:
            flash("Usa o email para o qual recebeste o convite.", "erro")
            return render_template("auth/registar.html",
                                   email_convite=email_convite, invite_token=invite_token)

        if not nome or not email or not password:
            flash("Preenche todos os campos obrigatórios.", "erro")
            return render_template("auth/registar.html",
                                   email_convite=email_convite, invite_token=invite_token)

        if password != confirmacao:
            flash("As palavras-passe não coincidem.", "erro")
            return render_template("auth/registar.html",
                                   email_convite=email_convite, invite_token=invite_token)

        if not senha_forte(password):
            flash("A palavra-passe deve ter pelo menos 8 caracteres, com maiúscula, minúscula e número.", "erro")
            return render_template("auth/registar.html",
                                   email_convite=email_convite, invite_token=invite_token)

        if User.query.filter_by(email=email).first():
            flash("Este email já está registado.", "erro")
            return render_template("auth/registar.html",
                                   email_convite=email_convite, invite_token=invite_token)

        user = User(nome=nome, email=email, instituicao=instituicao, curso=curso)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        registar_atividade(
            AtividadeLog.EVENTO_REGISTO, utilizador_id=user.id,
            detalhes={"email": user.email},
        )
        creditos_ao_registar(user)

        # Marca como registado na lista de espera
        entrada = ListaEspera.query.filter_by(email=email).first()
        if entrada:
            entrada.status = ListaEspera.STATUS_REGISTADO

        db.session.commit()

        login_user(user)
        email_boas_vindas(user)

        # Enviar email de confirmação
        token = gerar_token(user.email, SALT_CONFIRMACAO)
        url   = url_for("auth.confirmar_email", token=token, _external=True)
        email_confirmacao(user, url)

        flash(f"Bem-vindo(a), {user.nome}! Tens {user.creditos} créditos de boas-vindas.", "sucesso")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/registar.html",
                           email_convite=email_convite, invite_token=invite_token)


@auth_bp.route("/entrar", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email   = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        lembrar = request.form.get("lembrar") == "on"

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            registar_atividade(
                AtividadeLog.EVENTO_LOGIN_FALHADO,
                utilizador_id=user.id if user else None,
                detalhes={"email": email, "motivo": "credenciais_invalidas"},
            )
            db.session.commit()
            flash("Email ou palavra-passe incorretos.", "erro")
            return render_template("auth/entrar.html")

        if user.esta_eliminada:
            registar_atividade(
                AtividadeLog.EVENTO_LOGIN_FALHADO,
                utilizador_id=user.id,
                detalhes={"email": email, "motivo": "conta_eliminada"},
            )
            db.session.commit()
            flash("Esta conta foi eliminada.", "erro")
            return render_template("auth/entrar.html")

        if not user.is_active:
            registar_atividade(
                AtividadeLog.EVENTO_LOGIN_FALHADO,
                utilizador_id=user.id,
                detalhes={"email": email, "motivo": "conta_suspensa"},
            )
            db.session.commit()
            flash("Conta suspensa. Contacta o suporte.", "erro")
            return render_template("auth/entrar.html")

        login_user(user, remember=lembrar)
        registar_atividade(AtividadeLog.EVENTO_LOGIN, utilizador_id=user.id)
        db.session.commit()
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
    uid = current_user.id
    logout_user()
    registar_atividade(AtividadeLog.EVENTO_LOGOUT, utilizador_id=uid)
    db.session.commit()
    flash("Sessão terminada com sucesso.", "info")
    return redirect(url_for("auth.entrar"))


# ── Confirmação de email ───────────────────────────────────────────────────────

@auth_bp.route("/confirmar/<token>")
def confirmar_email(token):
    email = verificar_token(token, SALT_CONFIRMACAO, max_age=86400)  # 24h
    if not email:
        flash("O link de confirmação é inválido ou expirou.", "erro")
        return redirect(url_for("main.dashboard") if current_user.is_authenticated else url_for("auth.entrar"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Utilizador não encontrado.", "erro")
        return redirect(url_for("auth.entrar"))

    if user.email_verificado:
        flash("Email já confirmado anteriormente.", "info")
    else:
        user.email_verificado = True
        db.session.commit()
        flash("Email confirmado com sucesso!", "sucesso")

    return redirect(url_for("main.dashboard") if current_user.is_authenticated else url_for("auth.entrar"))


@auth_bp.route("/email-nao-confirmado")
@login_required
def email_nao_confirmado():
    if current_user.email_verificado:
        return redirect(url_for("main.dashboard"))
    return render_template("auth/email_nao_confirmado.html")


@auth_bp.route("/reenviar-confirmacao", methods=["POST"])
@login_required
def reenviar_confirmacao():
    if current_user.email_verificado:
        flash("O teu email já está confirmado.", "info")
        return redirect(url_for("main.dashboard"))

    token = gerar_token(current_user.email, SALT_CONFIRMACAO)
    url   = url_for("auth.confirmar_email", token=token, _external=True)
    email_confirmacao(current_user, url)
    flash("Email de confirmação reenviado. Verifica a tua caixa de entrada.", "sucesso")
    return redirect(url_for("main.dashboard"))


# ── Recuperação de palavra-passe ───────────────────────────────────────────────

@auth_bp.route("/recuperar", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def recuperar():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user  = User.query.filter_by(email=email).first()

        # Resposta igual para email existente ou não (evita enumeração)
        if user:
            token = gerar_token(user.email, SALT_RECUPERACAO)
            url   = url_for("auth.redefinir_senha", token=token, _external=True)
            email_recuperar_senha(user, url)

        flash("Se esse email estiver registado, receberás um link para redefinir a palavra-passe.", "sucesso")
        return redirect(url_for("auth.entrar"))

    return render_template("auth/recuperar.html")


@auth_bp.route("/redefinir/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    email = verificar_token(token, SALT_RECUPERACAO, max_age=3600)  # 1h
    if not email:
        flash("O link de recuperação é inválido ou expirou (válido por 1 hora).", "erro")
        return redirect(url_for("auth.recuperar"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Utilizador não encontrado.", "erro")
        return redirect(url_for("auth.entrar"))

    if request.method == "POST":
        password    = request.form.get("password", "")
        confirmacao = request.form.get("confirmacao", "")

        if not senha_forte(password):
            flash("A palavra-passe deve ter pelo menos 8 caracteres, com maiúscula, minúscula e número.", "erro")
            return render_template("auth/redefinir.html", token=token)

        if password != confirmacao:
            flash("As palavras-passe não coincidem.", "erro")
            return render_template("auth/redefinir.html", token=token)

        user.set_password(password)
        db.session.commit()
        flash("Palavra-passe atualizada. Podes entrar agora.", "sucesso")
        return redirect(url_for("auth.entrar"))

    return render_template("auth/redefinir.html", token=token)
