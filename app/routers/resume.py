from fastapi import APIRouter, UploadFile, File
from datetime import datetime

from app.services.s3_service import upload_file
from app.database.mongodb import resume_collection

router = APIRouter()

@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):

    file_data = await file.read()

    s3_key = upload_file(
        file_data=file_data,
        filename=file.filename
    )

    document = {
        "filename": file.filename,
        "s3_key": s3_key,
        "uploaded_at": datetime.utcnow()
    }

    result = resume_collection.insert_one(document)

    return {
        "resume_id": str(result.inserted_id),
        "s3_key": s3_key
    }