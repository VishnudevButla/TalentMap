# s3_utils.py
import boto3, os, uuid
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET = os.getenv("AWS_BUCKET_NAME")

def upload_resume(file_bytes, filename):
    key = f"resumes/{uuid.uuid4()}_{filename}"
    s3.put_object(Bucket=BUCKET, Key=key, Body=file_bytes, ContentType="application/pdf")
    return key

def get_presigned_url(key, expires=3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires
    )