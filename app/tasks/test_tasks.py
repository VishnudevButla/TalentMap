from app.core.celery_app import celery_app


@celery_app.task
def test_task():
    print("================================")
    print("TalentMap Celery task executed!")
    print("================================")

    return {
        "status": "success",
        "message": "Celery + Upstash Redis is working!"
    }