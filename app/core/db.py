"""
app/core/db.py — MongoDB Client & Collections

Initializes the MongoDB connection once when the app starts.
Exports collection objects that are imported directly by routes.

Collections:
- resume_collection    → stores raw resume metadata (filename, s3_key, timestamp)
- analysis_collection  → stores NLP + ML results per resume

Why a single module?
- Avoids creating a new connection on every request (expensive)
- One place to change DB name or add new collections
- Import pattern: from app.core.db import resume_collection

Connection uses:
- MONGODB_URI from config.py (loaded from .env)
- certifi for SSL certificates (required for MongoDB Atlas on macOS)
- ServerApi('1') to pin to MongoDB stable API version
"""

# import certifi
# from pymongo import MongoClient
# from pymongo.server_api import ServerApi
# from app.config import settings

# _client = MongoClient(
#     settings.mongodb_uri,
#     server_api=ServerApi('1'),
#     tlsCAFile=certifi.where()
# )

# db = _client["talentmap"]

# resume_collection   = db["resumes"]    # raw upload metadata
# analysis_collection = db["analyses"]   # NLP + ML results
