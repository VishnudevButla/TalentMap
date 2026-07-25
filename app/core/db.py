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
scheduler_locks_collection = db["scheduler_locks"]
# Single durable doc (_id: "global") holding the shared scan schedule/stats —
# no TTL, unlike scheduler_locks_collection which is a self-expiring lock.
agent_global_state_collection = db["agent_global_state"]

# AI Job Agent indexes — TTL bounds collection growth from the recurring
# scheduler, the unique index makes match writes race-safe (see matcher.py).
# Index creation failures shouldn't take the whole API down, so they're
# logged and swallowed rather than re-raised like the connection above.
try:
    _retention_seconds = settings.job_retention_days * 86400
    job_postings_collection.create_index("fetched_at", expireAfterSeconds=_retention_seconds)
    job_matches_collection.create_index("created_at", expireAfterSeconds=_retention_seconds)
    job_matches_collection.create_index(
        [("user_id", 1), ("job_id", 1), ("resume_id", 1)], unique=True
    )
    # Backs the live "new matches today" count (job_matches_collection.count_documents
    # with a user_id + created_at range) instead of a stored/duplicated counter.
    job_matches_collection.create_index([("user_id", 1), ("created_at", 1)])
    logger.info("AI Job Agent indexes ensured (retention=%dd)", settings.job_retention_days)
except Exception:
    logger.warning("Failed to ensure AI Job Agent indexes", exc_info=True)


def to_object_id(value: str):
    """Best-effort str -> ObjectId, returning the raw string if it isn't a valid ObjectId."""
    try:
        return ObjectId(value)
    except Exception:
        logger.debug("Invalid ObjectId: %s", value)
        return value
