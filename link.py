from s3_utils import upload_resume, get_presigned_url
from db import resumes_col
from datetime import datetime

def save_resume(file_bytes, filename, user_id):
    # Upload to S3
    key = upload_resume(file_bytes, filename)
    url = get_presigned_url(key)

    # Save reference in MongoDB
    doc = {
        "user_id": user_id,
        "s3_key": key,
        "s3_url": url,
        "uploaded_at": datetime.utcnow()
    }
    result = resumes_col.insert_one(doc)
    return str(result.inserted_id)