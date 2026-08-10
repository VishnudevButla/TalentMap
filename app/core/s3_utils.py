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

3. delete_file(s3_key) → None
   - Removes an object from the bucket (used by resume deletion)

S3 client is initialized once at module load using credentials from config.py
"""

import logging
from botocore.exceptions import ClientError
import boto3
import uuid
from app.config import settings

logger = logging.getLogger(__name__)

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region,
)

def upload_file(file_data: bytes, filename: str) -> str:
    key = f"resumes/{uuid.uuid4()}_{filename}"
    try:
        s3.put_object(
            Bucket=settings.aws_bucket_name,
            Key=key,
            Body=file_data
        )
    except ClientError as e:
        logger.error("S3 upload failed: key=%s error=%s", key, e)
        raise
    logger.info("Uploaded file to S3: key=%s", key)
    return key

def get_presigned_url(s3_key: str, expires: int = 3600) -> str:
    try:
        return s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": settings.aws_bucket_name,
                "Key": s3_key
            },
            ExpiresIn=expires
        )
    except ClientError as e:
        logger.error("S3 presigned URL generation failed: key=%s error=%s", s3_key, e)
        raise

def download_file(s3_key: str) -> bytes:
    """
    Download a file from S3.

    Args:
        s3_key: S3 object key.

    Returns:
        File contents as bytes.
    """

    try:
        response = s3.get_object(
            Bucket=settings.aws_bucket_name,
            Key=s3_key,
        )

        return response["Body"].read()

    except ClientError as e:
        logger.error("S3 download failed: key=%s error=%s", s3_key, e)
        raise RuntimeError(f"Failed to download file: {e}")

def delete_file(s3_key: str) -> None:
    """
    Delete a file from S3. Used by resume deletion (routes_history.py) —
    S3 delete_object is idempotent (no error if the key is already gone),
    so this is safe to call even if the object was already removed.
    """
    try:
        s3.delete_object(Bucket=settings.aws_bucket_name, Key=s3_key)
        logger.info("Deleted file from S3: key=%s", s3_key)
    except ClientError as e:
        logger.error("S3 delete failed: key=%s error=%s", s3_key, e)
        raise

## WE CAN USE THIS TO ACCESS THE RESUME FROM THE URL.......WE'll uncomment it while checking S3
# def get_presigned_url(
#     s3_key: str,
#     expires: int = 3600,
# ) -> str:
#     """
#     Generate a temporary download URL.

#     Args:
#         s3_key: S3 object key.
#         expires: Expiration time in seconds.

#     Returns:
#         Presigned URL.
#     """

#     try:
#         return s3.generate_presigned_url(
#             ClientMethod="get_object",
#             Params={
#                 "Bucket": settings.aws_bucket_name,
#                 "Key": s3_key,
#             },
#             ExpiresIn=expires,
#         )

#     except ClientError as e:
#         raise RuntimeError(f"Failed to generate presigned URL: {e}")