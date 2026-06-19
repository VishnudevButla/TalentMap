"""
scripts/seed_data.py — Database Seeding Script

This script populates MongoDB collections with mock data to bootstrap the TalentMap system
for testing, demonstration, and dashboard visualization.

Collections seeded:
1. job_descriptions_collection: Sets up target profiles to run cosine matches against.
2. resume_collection: Sample resume ingestion metadatas.
3. analysis_collection: Presaved results for the dashboard's "Historical Insights" view.

Flow:
1. Connect to MongoDB using database configurations (from app/core/db.py or config.py).
2. Clean existing collections to avoid duplicates (optional or configurable).
3. Insert mock records.
4. Output log success messages.
"""

from typing import List, Dict, Any

def get_mock_job_descriptions() -> List[Dict[str, Any]]:
    """
    Returns list of target Job Descriptions to write.
    """
    # - Return dictionary configurations representing JDs (e.g. title: "Python Engineer", key_skills: "Python, FastAPI").
    return []

def get_mock_resumes() -> List[Dict[str, Any]]:
    """
    Returns list of candidate resume upload metadata.
    """
    # - Return file metadata configurations (e.g. s3_key, file_name, uploader user_id).
    return []

def get_mock_analyses() -> List[Dict[str, Any]]:
    """
    Returns list of pre-analyzed profiles.
    """
    # - Return dictionary configurations (e.g. skills extracted, predicted role labels, estimated salaries).
    return []

def seed_database() -> None:
    """
    Cleans collections and inserts mock datasets.
    """
    # 1. Connect to client: client = MongoDB connection.
    # 2. Get collections (resume_collection, analysis_collection, job_descriptions_collection).
    # 3. Delete existing records: collection.delete_many({}).
    # 4. Insert mock lists: collection.insert_many(data).
    # 5. Log completion status.
    pass

if __name__ == "__main__":
    seed_database()
