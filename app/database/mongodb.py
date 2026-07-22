import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

_client = MongoClient(
    os.getenv("MONGODB_URI"),
    server_api=ServerApi('1'),
    tlsCAFile=certifi.where()
)

db = _client["talentmap"]

resume_collection = db["resumes"]
user_collection = db["users"]
job_collection = db["jobs"]
