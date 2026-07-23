from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
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
