"""
app/core/s3_utils.py — AWS S3 Utilities

Two main functions used across the app:

1. upload_file(file_data, filename) → s3_key
   - Generates a unique filename using UUID to avoid collisions
   - Uploads raw bytes to S3 bucket under the "resumes/" prefix
   - Returns the S3 key (path) so we can reference it later

2. get_presigned_url(s3_key, expires=3600) → url
   - Generates a temporary signed URL for the stored file
   - Default expiry: 1 hour (3600 seconds)
   - Used when you want to give the frontend a direct download link
     without making the S3 bucket fully public

S3 client is initialized once at module load using credentials from config.py
"""

import boto3
import uuid
from app.config import settings

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region,
)

def upload_file(file_data: bytes, filename: str) -> str:
    key = f"resumes/{uuid.uuid4()}_{filename}"
    s3.put_object(
        Bucket=settings.aws_bucket_name,
        Key=key,
        Body=file_data
    )
    return key

def get_presigned_url(s3_key: str, expires: int = 3600) -> str:
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.aws_bucket_name,
            "Key": s3_key
        },
        ExpiresIn=expires
    )
