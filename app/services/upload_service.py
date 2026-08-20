import io
import os
import uuid
import hashlib
import unicodedata
import re
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename


def _usar_r2() -> bool:
    return bool(os.environ.get("R2_ENDPOINT"))


def extensao_permitida(filename: str) -> bool:
    permitidas = current_app.config["ALLOWED_EXTENSIONS"]
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in permitidas
    )


def gerar_nome_unico(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def guardar_ficheiro(file_obj, subfolder: str = "") -> dict:
    nome_original = secure_filename(file_obj.filename)

    if not extensao_permitida(nome_original):
        raise ValueError(f"Tipo de ficheiro não permitido: {nome_original}")

    nome_guardado = gerar_nome_unico(nome_original)
    tipo = Path(nome_guardado).suffix.lstrip(".")
    data = file_obj.read()
    tamanho = len(data)
    hash_ficheiro = hashlib.sha256(data).hexdigest()

    key = f"{subfolder}/{nome_guardado}" if subfolder else nome_guardado

    if _usar_r2():
        from app.services.r2_service import upload_bytes
        upload_bytes(data, key, tipo)
        if tipo in {"png", "jpg", "jpeg", "gif", "webp"}:
            _gerar_thumbnail_r2(data, subfolder, nome_guardado, tipo)
    else:
        upload_base = current_app.config["UPLOAD_FOLDER"]
        destino_dir = os.path.join(upload_base, subfolder) if subfolder else upload_base
        os.makedirs(destino_dir, exist_ok=True)
        caminho_completo = os.path.join(destino_dir, nome_guardado)
        with open(caminho_completo, "wb") as f:
            f.write(data)
        if tipo in {"png", "jpg", "jpeg", "gif", "webp"}:
            _gerar_thumbnail(caminho_completo, destino_dir, nome_guardado)

    return {
        "nome_original": nome_original,
        "nome_guardado": nome_guardado,
        "path_relativo": key,
        "tipo": tipo,
        "tamanho": tamanho,
        "hash": hash_ficheiro,
    }


def _gerar_thumbnail_r2(data: bytes, subfolder: str, nome: str, tipo: str):
    try:
        from PIL import Image
        from app.services.r2_service import upload_bytes
        with Image.open(io.BytesIO(data)) as img:
            img.thumbnail((300, 300))
            out = io.BytesIO()
            fmt = "JPEG" if tipo in {"jpg", "jpeg"} else tipo.upper()
            img.save(out, format=fmt)
        thumb_key = f"{subfolder}/thumbs/{nome}" if subfolder else f"thumbs/{nome}"
        upload_bytes(out.getvalue(), thumb_key, tipo)
    except Exception:
        pass


def _gerar_thumbnail(caminho_original: str, destino_dir: str, nome: str):
    try:
        from PIL import Image
        thumb_dir = os.path.join(destino_dir, "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, nome)
        with Image.open(caminho_original) as img:
            img.thumbnail((300, 300))
            img.save(thumb_path)
    except Exception:
        pass


def calcular_hash(caminho_completo: str) -> str:
    sha256 = hashlib.sha256()
    with open(caminho_completo, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def nome_download(titulo: str, tipo: str) -> str:
    s = unicodedata.normalize("NFD", titulo.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "_", s.strip())
    s = s.strip("_-")[:80] or "material"
    return f"{s}.{tipo}"


def apagar_ficheiro(path_relativo: str):
    if _usar_r2():
        from app.services.r2_service import delete_object
        delete_object(path_relativo)
        pasta = path_relativo.rsplit("/", 1)[0] if "/" in path_relativo else ""
        nome = path_relativo.rsplit("/", 1)[-1]
        thumb_key = f"{pasta}/thumbs/{nome}" if pasta else f"thumbs/{nome}"
        delete_object(thumb_key)
    else:
        upload_base = current_app.config["UPLOAD_FOLDER"]
        caminho = os.path.join(upload_base, path_relativo)
        if os.path.exists(caminho):
            os.remove(caminho)
        nome = os.path.basename(path_relativo)
        pasta = os.path.dirname(path_relativo)
        thumb = os.path.join(upload_base, pasta, "thumbs", nome)
        if os.path.exists(thumb):
            os.remove(thumb)
