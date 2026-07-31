from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings


class ObjectStorage:
    """S3-compatible storage for source and derived artifacts."""

    def __init__(self) -> None:
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "path",
                },
            ),
        )

    def put_object(
        self,
        *,
        bucket: str,
        object_key: str,
        content: bytes,
        media_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=media_type,
            Metadata=metadata or {},
        )

    def get_object_bytes(
        self,
        *,
        bucket: str,
        object_key: str,
    ) -> bytes:
        response = self.client.get_object(
            Bucket=bucket,
            Key=object_key,
        )

        body = response["Body"]

        try:
            return body.read()
        finally:
            body.close()

    def delete_object(
        self,
        *,
        bucket: str,
        object_key: str,
    ) -> None:
        self.client.delete_object(
            Bucket=bucket,
            Key=object_key,
        )

    def put_source_document(
        self,
        *,
        object_key: str,
        content: bytes,
        media_type: str,
        metadata: dict[str, str],
    ) -> None:
        self.put_object(
            bucket=settings.s3_bucket_source_invoices,
            object_key=object_key,
            content=content,
            media_type=media_type,
            metadata=metadata,
        )

    def delete_source_document(
        self,
        *,
        object_key: str,
    ) -> None:
        self.delete_object(
            bucket=settings.s3_bucket_source_invoices,
            object_key=object_key,
        )

    def put_page_artifact(
        self,
        *,
        object_key: str,
        content: bytes,
        metadata: dict[str, str],
    ) -> None:
        self.put_object(
            bucket=settings.s3_bucket_derived_pages,
            object_key=object_key,
            content=content,
            media_type="image/png",
            metadata=metadata,
        )


@lru_cache
def get_object_storage() -> ObjectStorage:
    return ObjectStorage()