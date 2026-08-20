import os
import boto3
from botocore.config import Config

_CONTENT_TYPES = {
    "pdf":  "application/pdf",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "gif":  "image/gif",
    "webp": "image/webp",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _bucket():
    return os.environ.get("R2_BUCKET", "ponto24-materiais")


def upload_bytes(data: bytes, key: str, tipo: str) -> None:
    ct = _CONTENT_TYPES.get(tipo, "application/octet-stream")
    _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=ct)


def copy_object(old_key: str, new_key: str) -> None:
    """Copia um objeto para uma nova key. Levanta exceção em falha (não engole,
    ao contrário de delete_object) — o caller precisa de saber se a cópia falhou
    antes de apagar o original."""
    _client().copy_object(Bucket=_bucket(), CopySource={"Bucket": _bucket(), "Key": old_key}, Key=new_key)


def delete_object(key: str) -> None:
    try:
        _client().delete_object(Bucket=_bucket(), Key=key)
    except Exception:
        pass


def presigned_url(key: str, expires: int = 3600, download_name: str = None) -> str:
    params = {"Bucket": _bucket(), "Key": key}
    if download_name:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
    return _client().generate_presigned_url("get_object", Params=params, ExpiresIn=expires)
