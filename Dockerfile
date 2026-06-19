# Dockerfile for TalentMap Services
# This file sets up a containerized environment running both the FastAPI backend and Streamlit dashboard.
# We use a multi-stage build to keep production images small and secure.

# Stage 1: Build & dependency resolver stage
FROM python:3.10-slim as builder

# 1. Set working directory to /tmp/build.
# 2. Copy requirements.txt file.
# 3. Compile dependencies and install wheels to a local cache directory.
# 4. (For example, downloading spaCy's english model: python -m spacy download en_core_web_sm)

# Stage 2: Final runner stage
FROM python:3.10-slim as runner

# 1. Establish app workdir: WORKDIR /workspace/talentmap
# 2. Copy installed package environments from builder stage to speed up container booting.
# 3. Copy application files (app/, dashboard/, scripts/).
# 4. Copy configuration variables (.env.example, requirements.txt).
# 5. Expose necessary ports:
#    - FastAPI backend: EXPOSE 8000
#    - Streamlit frontend: EXPOSE 8501
# 6. Set environment configs (PYTHONUNBUFFERED=1, etc.).
# 7. Run entrypoint script (e.g. supervisord, shell runner) starting FastAPI and Streamlit concurrently.
