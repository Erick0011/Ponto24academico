import io
import os
import shutil
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


# ── Mover ficheiros para pastas (Sistema de Pastas) ─────────────────────────────

def slugify(texto: str) -> str:
    """Normaliza um nome livre (ex: nome de pasta) para um segmento de caminho seguro."""
    s = texto.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "_", s).strip("_") or "pasta"


def caminho_pasta_para_subfolder(pasta) -> str:
    """Constrói o subfolder de armazenamento a partir da árvore de pastas,
    ex: 'pastas/isaf/informatica/3_semestre'."""
    nomes, no = [], pasta
    while no is not None:
        nomes.append(slugify(no.nome))
        no = no.parent
    return "pastas/" + "/".join(reversed(nomes))


def mover_ficheiro(material, novo_subfolder: str) -> dict:
    """Move o ficheiro (e a thumbnail, se for imagem) de um Material para um novo
    subfolder. NÃO toca na base de dados — devolve o novo path_relativo para o
    caller aplicar só depois de confirmado o sucesso aqui.

    Levanta exceção em caso de falha; nesse caso nada foi alterado de forma
    irreversível (local: shutil.move só corre no fim; R2: copy_object só é seguido
    de delete_object depois de a cópia ter sido confirmada).
    """
    nome_ficheiro = os.path.basename(material.ficheiro_path)
    novo_path = f"{novo_subfolder}/{nome_ficheiro}"
    if novo_path == material.ficheiro_path:
        return {"ficheiro_path": material.ficheiro_path}  # já está lá, no-op

    if _usar_r2():
        from app.services.r2_service import copy_object, delete_object
        copy_object(material.ficheiro_path, novo_path)  # levanta exceção se falhar
        if material.e_imagem:
            old_thumb = f"{os.path.dirname(material.ficheiro_path)}/thumbs/{nome_ficheiro}"
            try:
                copy_object(old_thumb, f"{novo_subfolder}/thumbs/{nome_ficheiro}")
            except Exception:
                pass  # thumb é regenerável/opcional, não bloqueia o material principal
        delete_object(material.ficheiro_path)
        if material.e_imagem:
            delete_object(f"{os.path.dirname(material.ficheiro_path)}/thumbs/{nome_ficheiro}")
    else:
        upload_base = current_app.config["UPLOAD_FOLDER"]
        old_full = os.path.join(upload_base, material.ficheiro_path)
        novo_dir = os.path.join(upload_base, novo_subfolder)
        os.makedirs(novo_dir, exist_ok=True)
        shutil.move(old_full, os.path.join(novo_dir, nome_ficheiro))  # levanta exceção se falhar
        if material.e_imagem:
            old_thumb = os.path.join(upload_base, os.path.dirname(material.ficheiro_path), "thumbs", nome_ficheiro)
            if os.path.exists(old_thumb):
                novo_thumb_dir = os.path.join(novo_dir, "thumbs")
                os.makedirs(novo_thumb_dir, exist_ok=True)
                shutil.move(old_thumb, os.path.join(novo_thumb_dir, nome_ficheiro))

    return {"ficheiro_path": novo_path}


def mover_grupo_para_pasta(materiais: list, pasta) -> dict:
    """Move TODOS os ficheiros de um grupo (ou de um único material) para a pasta
    destino. All-or-nothing: só devolve ok=True se TODOS moverem com sucesso; em
    falha parcial tenta reverter (best-effort) os já movidos. O caller NUNCA deve
    tocar na base de dados a não ser que 'ok' seja True.
    """
    subfolder = caminho_pasta_para_subfolder(pasta)
    movidos = []  # [(material, path_antigo, path_novo)]
    try:
        for m in materiais:
            path_antigo = m.ficheiro_path
            resultado = mover_ficheiro(m, subfolder)
            movidos.append((m, path_antigo, resultado["ficheiro_path"]))
        return {"ok": True, "novos_paths": {m.id: novo for m, _, novo in movidos}}
    except Exception as e:
        for m, path_antigo, path_novo in movidos:
            try:
                subfolder_antigo = os.path.dirname(path_antigo)
                m.ficheiro_path = path_novo  # temporário, para mover_ficheiro calcular a partir daqui
                mover_ficheiro(m, subfolder_antigo)
                m.ficheiro_path = path_antigo
            except Exception:
                pass  # rollback best-effort; o erro original é o que importa reportar
        return {"ok": False, "erro": str(e)}
