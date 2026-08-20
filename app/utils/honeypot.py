from flask import request


def honeypot_preenchido(campo: str = "website") -> bool:
    """True se o campo-armadilha anti-bot foi preenchido (indício de bot)."""
    return bool(request.form.get(campo, "").strip())
