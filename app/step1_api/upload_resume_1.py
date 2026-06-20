from fastapi import APIRouter, UploadFile, File, Depends
from datetime import datetime
from app.core.s3_utils import upload_file
from app.core.db import resume_collection
from app.schemas.resume_schema import ResumeUploadResponse
from app.core.security import get_current_user

router = APIRouter()

@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    file_data = await file.read()

    s3_key = upload_file(
        file_data=file_data,
        filename=file.filename
    )

    document = {
        "user_id": user_id,
        "filename": file.filename,
        "s3_key": s3_key,
        "status": "uploaded"
    }

    result = resume_collection.insert_one(document)

    return ResumeUploadResponse(
        resume_id=str(result.inserted_id),
        s3_key=s3_key,
        user_id=user_id,
        status="SUCCESS",
        uploaded_at=datetime.utcnow()
    )
