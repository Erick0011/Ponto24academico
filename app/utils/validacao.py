import re


def senha_forte(password: str) -> bool:
    """Mín. 8 caracteres, com maiúscula, minúscula e dígito."""
    return (
        len(password) >= 8
        and bool(re.search(r"[A-Z]", password))
        and bool(re.search(r"[a-z]", password))
        and bool(re.search(r"\d", password))
    )
