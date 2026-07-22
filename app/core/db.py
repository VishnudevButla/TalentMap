"""
app/core/db.py — MongoDB Client & Collections

Initializes the MongoDB Atlas connection once when the app starts. This
project always runs against Atlas — if the connection fails (bad
credentials, IP allowlist, network), it fails loudly at startup rather
than silently degrading to a local dev store.
"""

import sys
import logging
from pathlib import Path
from bson.objectid import ObjectId
import certifi
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from app.config import settings

logger = logging.getLogger(__name__)

# Add project root to sys.path to allow running this script directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    _client = MongoClient(
        settings.mongodb_uri,
        server_api=ServerApi('1'),
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000
    )
    _client.admin.command('ping')
    db = _client["talentmap"]
    logger.info("MongoDB connection established")
except Exception:
    # Never log settings.mongodb_uri — it embeds credentials. exc_info lets
    # pymongo's own exception surface, which already redacts passwords.
    logger.critical("MongoDB connection failed", exc_info=True)
    raise

resume_collection        = db["resumes"]
analysis_collection      = db["analyses"]
user_collection          = db["users"]
job_postings_collection  = db["job_postings"]
job_matches_collection   = db["job_matches"]
agent_state_collection   = db["agent_state"]
activity_log_collection  = db["activity_log"]
user_settings_collection = db["user_settings"]


def to_object_id(value: str):
    """Best-effort str -> ObjectId, returning the raw string if it isn't a valid ObjectId."""
    try:
        return ObjectId(value)
    except Exception:
        logger.debug("Invalid ObjectId: %s", value)
        return value
