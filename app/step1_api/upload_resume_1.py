import logging
from fastapi import APIRouter, UploadFile, File, Depends
from datetime import datetime
from app.core.s3_utils import upload_file
from app.core.db import resume_collection
from app.schemas.resume_schema import ResumeUploadResponse
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    logger.info("Resume upload started: user_id=%s", user_id)

    try:
        file_data = await file.read()

        s3_key = upload_file(
            file_data=file_data,
            filename=file.filename
        )

        document = {
            "user_id": user_id,
            "filename": file.filename,
            "s3_key": s3_key,
            "status": "uploaded",
            "uploaded_at": datetime.utcnow(),
        }

        result = resume_collection.insert_one(document)
    except Exception:
        logger.exception("Resume upload failed: user_id=%s", user_id)
        raise

    resume_id = str(result.inserted_id)
    logger.info("Resume upload completed: user_id=%s resume_id=%s", user_id, resume_id)

    return ResumeUploadResponse(
        resume_id=resume_id,
        s3_key=s3_key,
        user_id=user_id,
        status="SUCCESS",
        uploaded_at=datetime.utcnow()
    )
