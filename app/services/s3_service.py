import boto3
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET = os.getenv("AWS_BUCKET_NAME")


def upload_file(file_data: bytes, filename: str) -> str:
    """Upload file bytes to S3 and return the S3 key."""
    key = f"resumes/{uuid.uuid4()}_{filename}"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=file_data,
        ContentType="application/pdf"
    )
    return key


def get_presigned_url(key: str, expires: int = 3600) -> str:
    """Generate a presigned URL for a given S3 key."""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires
    )
