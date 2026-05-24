import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import render_template, current_app

logger = logging.getLogger(__name__)


def _smtp_config():
    # Suporta tanto EMAIL_USER/EMAIL_PASS como MAIL_USERNAME/MAIL_PASSWORD
    username = os.environ.get("EMAIL_USER") or os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("EMAIL_PASS") or os.environ.get("MAIL_PASSWORD", "")
    # Se for Gmail, usa smtp.gmail.com como padrão
    default_server = "smtp.gmail.com" if "@gmail.com" in username else ""
    return {
        "server":   os.environ.get("MAIL_SERVER", default_server),
        "port":     int(os.environ.get("MAIL_PORT", 587)),
        "use_tls":  os.environ.get("MAIL_USE_TLS", "true").lower() == "true",
        "username": username,
        "password": password,
        "sender":   os.environ.get("MAIL_DEFAULT_SENDER", username),
    }


def enviar_email(destinatario, assunto, template_html, contexto=None):
    """
    Envia um email HTML. Silencia erros se SMTP não estiver configurado.
    template_html: caminho relativo em templates/ (ex: 'email/boas_vindas.html')
    """
    cfg = _smtp_config()
    if not cfg["server"] or not cfg["username"]:
        logger.debug("SMTP não configurado — email não enviado para %s", destinatario)
        return False

    try:
        from flask import has_request_context
        if has_request_context():
            html_body = render_template(template_html, **(contexto or {}))
        else:
            # CLI ou tarefa assíncrona — cria contexto de request temporário
            with current_app.test_request_context():
                html_body = render_template(template_html, **(contexto or {}))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = f"Ponto 24 Académico <{cfg['sender']}>"
        msg["To"]      = destinatario
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(cfg["server"], cfg["port"]) as smtp:
            if cfg["use_tls"]:
                smtp.starttls()
            smtp.login(cfg["username"], cfg["password"])
            smtp.sendmail(cfg["sender"], destinatario, msg.as_string())

        logger.info("Email enviado para %s: %s", destinatario, assunto)
        return True

    except Exception as e:
        logger.warning("Falha ao enviar email para %s: %s", destinatario, e)
        return False


# ─── Funções de alto nível ───────────────────────────────────────────────────

def email_boas_vindas(user):
    enviar_email(
        destinatario=user.email,
        assunto="Bem-vindo(a) ao Ponto 24 Académico!",
        template_html="email/boas_vindas.html",
        contexto={"user": user},
    )


def email_material_aprovado(material):
    enviar_email(
        destinatario=material.autor.email,
        assunto=f"Material aprovado — {material.titulo_base}",
        template_html="email/material_aprovado.html",
        contexto={"material": material, "user": material.autor},
    )


def email_confirmacao(user, url_confirmacao):
    enviar_email(
        destinatario=user.email,
        assunto="Confirma o teu email — Ponto 24 Académico",
        template_html="email/confirmar_email.html",
        contexto={"user": user, "url": url_confirmacao},
    )


def email_recuperar_senha(user, url_recuperacao):
    enviar_email(
        destinatario=user.email,
        assunto="Recuperação de palavra-passe — Ponto 24 Académico",
        template_html="email/recuperar_senha.html",
        contexto={"user": user, "url": url_recuperacao},
    )


def email_material_rejeitado(material, motivo=None):
    enviar_email(
        destinatario=material.autor.email,
        assunto=f"Material rejeitado — {material.titulo_base}",
        template_html="email/material_rejeitado.html",
        contexto={"material": material, "user": material.autor, "motivo": motivo},
    )


def email_novo_material_pendente(material, moderador, url_rever):
    enviar_email(
        destinatario=moderador.email,
        assunto=f"[P24] Novo material para moderar — {material.titulo_base}",
        template_html="email/novo_material.html",
        contexto={"material": material, "moderador": moderador, "url": url_rever},
    )


def email_convite_acesso(entrada, url_convite):
    enviar_email(
        destinatario=entrada.email,
        assunto="O teu acesso antecipado ao Ponto 24 Académico chegou!",
        template_html="email/convite_acesso.html",
        contexto={"entrada": entrada, "url": url_convite},
    )
