import os
import uuid
import hashlib
import unicodedata
import re
from pathlib import Path
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx"}


def extensao_permitida(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def gerar_nome_unico(filename: str) -> str:
    """Gera nome de ficheiro único preservando a extensão original."""
    ext = Path(filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def guardar_ficheiro(file_obj, subfolder: str = "") -> dict:
    """
    Guarda o ficheiro no disco de forma segura.

    Retorna dict com:
        - nome_original: nome original do ficheiro
        - nome_guardado: nome único gerado
        - path_relativo: caminho relativo a UPLOAD_FOLDER
        - tipo: extensão (sem ponto)
        - tamanho: tamanho em bytes
    """
    nome_original = secure_filename(file_obj.filename)

    if not extensao_permitida(nome_original):
        raise ValueError(f"Tipo de ficheiro não permitido: {nome_original}")

    nome_guardado = gerar_nome_unico(nome_original)
    upload_base = current_app.config["UPLOAD_FOLDER"]
    destino_dir = os.path.join(upload_base, subfolder)
    os.makedirs(destino_dir, exist_ok=True)

    caminho_completo = os.path.join(destino_dir, nome_guardado)
    file_obj.save(caminho_completo)

    tamanho = os.path.getsize(caminho_completo)
    tipo = Path(nome_guardado).suffix.lstrip(".")
    hash_ficheiro = calcular_hash(caminho_completo)

    # Gera thumbnail para imagens
    if tipo in {"png", "jpg", "jpeg", "gif", "webp"}:
        _gerar_thumbnail(caminho_completo, destino_dir, nome_guardado)

    path_relativo = os.path.join(subfolder, nome_guardado) if subfolder else nome_guardado

    return {
        "nome_original": nome_original,
        "nome_guardado": nome_guardado,
        "path_relativo": path_relativo,
        "tipo": tipo,
        "tamanho": tamanho,
        "hash": hash_ficheiro,
    }


def _gerar_thumbnail(caminho_original: str, destino_dir: str, nome: str):
    """Gera uma thumbnail de 300x300 para imagens."""
    try:
        thumb_dir = os.path.join(destino_dir, "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, nome)

        with Image.open(caminho_original) as img:
            img.thumbnail((300, 300))
            img.save(thumb_path)
    except Exception:
        pass  # Thumbnail opcional, não bloqueia o upload


def calcular_hash(caminho_completo: str) -> str:
    """Calcula SHA-256 do conteúdo do ficheiro."""
    sha256 = hashlib.sha256()
    with open(caminho_completo, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def nome_download(titulo: str, tipo: str) -> str:
    """Gera nome de ficheiro seguro para download a partir do título do material."""
    s = unicodedata.normalize("NFD", titulo.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "_", s.strip())
    s = s.strip("_-")[:80] or "material"
    return f"{s}.{tipo}"


def apagar_ficheiro(path_relativo: str):
    """Remove um ficheiro do disco (e a sua thumbnail se existir)."""
    upload_base = current_app.config["UPLOAD_FOLDER"]
    caminho = os.path.join(upload_base, path_relativo)

    if os.path.exists(caminho):
        os.remove(caminho)

    # Tenta remover thumbnail
    nome = os.path.basename(path_relativo)
    pasta = os.path.dirname(path_relativo)
    thumb = os.path.join(upload_base, pasta, "thumbs", nome)
    if os.path.exists(thumb):
        os.remove(thumb)
