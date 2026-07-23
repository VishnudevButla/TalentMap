# email_test.py — test Resend email sending standalone
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from app.core.logger import setup_logging
setup_logging()

# Patch MongoClient before importing app.core.db so Mongo ping failure is bypassed
with patch("pymongo.MongoClient"):
    import app.core.db as db_module

# Mock job object returned by MongoDB
dummy_job_id = "60c72b2f9b1d8b2b8c8b4567"
mock_job = {
    "_id": dummy_job_id,
    "title": "Senior Python & AI Engineer",
    "company": "TalentMap AI Labs",
    "location": "Remote",
    "url": "https://example.com/apply",
    "salary_min": 120000,
    "salary_max": 150000,
}

db_module.job_postings_collection = MagicMock()
db_module.job_postings_collection.find.return_value = [mock_job]

from app.step4_agent.email_alerts import send_match_alert_email

fake_matches = [
    {
        "job_id": dummy_job_id,
        "match_score": 95,
        "status": "excellent",
    },
]

# Send test alert (uses Resend API if RESEND_API_KEY is set in .env)
result = send_match_alert_email(
    to_email="17kc1727.xi@gmail.com",
    matches=fake_matches,
)

print("\n----------------------------------------")
print("Email sent:", result)
print("----------------------------------------\n")
