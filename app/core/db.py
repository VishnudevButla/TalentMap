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
from pymongo.errors import OperationFailure
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
# Single-use Google OAuth handoff tokens (app/routers/oauth_google.py) —
# _id is the random token itself, so find_one_and_delete() is an atomic
# claim-and-burn. TTL index below is just garbage collection for
# never-redeemed tokens, not the single-use guarantee itself.
oauth_handoff_collection = db["oauth_handoffs"]

def _ensure_ttl_index(collection, field: str, seconds: int) -> None:
    """
    create_index() can't silently change an existing TTL index's
    expireAfterSeconds — Mongo raises IndexOptionsConflict (code 85) if
    JOB_RETENTION_DAYS changes in .env after the index already exists with
    the old value. Drop and recreate on that specific conflict instead of
    leaving the old window in place forever (which is what was happening).
    """
    try:
        collection.create_index(field, expireAfterSeconds=seconds)
    except OperationFailure as exc:
        if exc.code != 85:
            raise
        collection.drop_index(f"{field}_1")
        collection.create_index(field, expireAfterSeconds=seconds)


# AI Job Agent indexes — TTL bounds collection growth from the recurring
# scheduler, the unique index makes match writes race-safe (see matcher.py).
# Index creation failures shouldn't take the whole API down, so they're
# logged and swallowed rather than re-raised like the connection above.
try:
    _retention_seconds = settings.job_retention_days * 86400
    _ensure_ttl_index(job_postings_collection, "fetched_at", _retention_seconds)
    _ensure_ttl_index(job_matches_collection, "created_at", _retention_seconds)
    # Generous relative to the 60s app-level expiry checked at issue time —
    # this index only needs to clean up tokens nobody ever redeemed.
    _ensure_ttl_index(oauth_handoff_collection, "created_at", 300)
    job_matches_collection.create_index(
        [("user_id", 1), ("job_id", 1), ("resume_id", 1)], unique=True
    )
    # Backs the live "new matches today" count (job_matches_collection.count_documents
    # with a user_id + created_at range) instead of a stored/duplicated counter.
    job_matches_collection.create_index([("user_id", 1), ("created_at", 1)])
    # Backs job_matches_collection.find({"user_id": ...}).sort("match_score", -1)
    # — dashboard/matches/agent/market-trends all run this; without an index
    # covering the sort field it was a full collection scan every time.
    job_matches_collection.create_index([("user_id", 1), ("match_score", -1)])
    # Backs analysis_collection.find({"user_id": ...}).sort("analyzed_at", -1).limit(1)
    # — the single most frequently run query in the app (every dashboard
    # load, every matcher run), previously with no index at all.
    analysis_collection.create_index([("user_id", 1), ("analyzed_at", -1)])
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
