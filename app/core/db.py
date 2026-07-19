"""
app/core/db.py — MongoDB Client & Collections (with local fallback)

Initializes the MongoDB connection once when the app starts.
If the connection fails (e.g. due to IP whitelisting or bad credentials),
falls back gracefully to local file-based database storage (.dev_db_*.json)
so development and testing can proceed seamlessly.
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from bson.objectid import ObjectId
import certifi
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from app.config import settings

# Add project root to sys.path to allow running this script directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

class FallbackCollection:
    def __init__(self, name: str):
        self.name = name
        self.file_path = project_root / f".dev_db_{name}.json"
        if not self.file_path.exists():
            self.file_path.write_text("{}", encoding="utf-8")

    def _read_data(self):
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_data(self, data):
        self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _serialize_val(self, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: self._serialize_val(val) for k, val in v.items()}
        if isinstance(v, list):
            return [self._serialize_val(val) for val in v]
        return v

    def find_one(self, filter_dict):
        data = self._read_data()
        for doc_id, doc in data.items():
            match = True
            for k, v in filter_dict.items():
                if k == "_id":
                    val_str = str(v)
                    if doc.get("_id") != val_str and doc_id != val_str:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                res = doc.copy()
                if "_id" in res:
                    res["_id"] = ObjectId(res["_id"])
                return res
        return None

    class InsertOneResult:
        def __init__(self, inserted_id):
            self.inserted_id = inserted_id

    def insert_one(self, document):
        data = self._read_data()
        doc = document.copy()
        if "_id" not in doc:
            doc_id = ObjectId()
            doc["_id"] = doc_id
        else:
            doc_id = doc["_id"]
            
        str_id = str(doc_id)
        doc_store = self._serialize_val(doc)
        doc_store["_id"] = str_id

        data[str_id] = doc_store
        self._write_data(data)
        return self.InsertOneResult(doc_id)

    def find(self, filter_dict=None):
        if filter_dict is None:
            filter_dict = {}
        data = self._read_data()
        results = []
        for doc_id, doc in data.items():
            match = True
            for k, v in filter_dict.items():
                if k == "_id":
                    val_str = str(v)
                    if doc.get("_id") != val_str and doc_id != val_str:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                res = doc.copy()
                if "_id" in res:
                    res["_id"] = ObjectId(res["_id"])
                results.append(res)
        return results

# Build URI with credentials replacement
uri = settings.mongodb_uri
if settings.mongodb_password and "<db_password>" in uri:
    uri = uri.replace("<db_password>", settings.mongodb_password)
if settings.mongodb_username and "prithvisd6_db_user" in uri:
    uri = uri.replace("prithvisd6_db_user", settings.mongodb_username)

use_mongodb = False
db = None

try:
    _client = MongoClient(
        uri,
        server_api=ServerApi('1'),
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=2000
    )
    _client.admin.command('ping')
    db = _client["talentmap"]
    print("SUCCESS: Connected to MongoDB Atlas!")
    use_mongodb = True
except Exception as db_err:
    print(f"WARNING: MongoDB Atlas connection failed: {db_err}")
    print("Falling back to local file-based database for development.")
    use_mongodb = False

if use_mongodb:
    resume_collection   = db["resumes"]
    analysis_collection = db["analyses"]
    user_collection     = db["users"]
else:
    resume_collection   = FallbackCollection("resumes")
    analysis_collection = FallbackCollection("analyses")
    user_collection     = FallbackCollection("users")
