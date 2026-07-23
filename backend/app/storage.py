from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


def _client(endpoint_url: str | None = None):
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def _ensure_bucket(client) -> str:
    bucket = get_settings().s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)
    return bucket


def upload_report(local_path: Path, object_key: str) -> str:
    """Upload un PDF vers MinIO/S3 et renvoie son URI (`s3://bucket/key`)."""
    client = _client()
    bucket = _ensure_bucket(client)
    client.upload_file(str(local_path), bucket, object_key)
    return f"s3://{bucket}/{object_key}"


def presigned_url_for(storage_location: str, expires_in: int = 3600) -> str:
    """Génère un lien de téléchargement temporaire pour une URI `s3://bucket/key`.

    Signée avec `s3_public_endpoint_url` (pas `s3_endpoint_url`) : la signature
    est un calcul local (pas d'appel réseau), mais le lien doit rester
    utilisable par un client externe au réseau Docker — `minio:9000` n'y est
    pas résoluble, `localhost:9000` (port publié sur l'hôte) l'est.
    """
    if not storage_location.startswith("s3://"):
        raise ValueError(f"not an s3 uri: {storage_location}")
    bucket, _, key = storage_location.removeprefix("s3://").partition("/")
    client = _client(endpoint_url=get_settings().s3_public_endpoint_url)
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )
