# TalentMap — Resume Analysis Pipeline & AI Platform

TalentMap is a modular, AI-powered system that analyzes resumes, extracts entities (skills, education, experience), matches candidates to job descriptions, and predicts job roles and salary bands.

This repository is structured as an architectural blueprint, containing commented skeleton files that explain every component in detail.

---

## Folder Architecture

```
TalentMap/
├── app/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py               # Environment variable loader (Pydantic BaseSettings)
│   │
│   ├── api/
│   │   ├── routes_resume.py     # Endpoint: POST /upload-resume (S3 & MongoDB storage)
│   │   ├── routes_analyze.py    # Endpoint: POST /analyze (Runs parser -> NLP -> ML predictions)
│   │   └── routes_history.py    # Endpoint: GET /history/{user_id} (Retrieves historical results)
│   │
│   ├── core/
│   │   ├── s3_utils.py          # Boto3 S3 upload/download helper scripts
│   │   ├── db.py                # MongoDB connection initializations & collections
│   │   └── security.py          # JWT user authorization functions (optional)
│   │
│   ├── nlp/
│   │   ├── pdf_parser.py        # PDF binary to plain text extractor
│   │   ├── preprocess.py        # Text cleaning, normalization, tokenization
│   │   ├── ner_extractor.py     # Named Entity Recognition (spaCy) for skills, education, and experience
│   │   └── embeddings.py        # TF-IDF / BERT vectorization and Cosine Similarity calculation
│   │
│   ├── ml/
│   │   ├── train_role_model.py  # Script training the job role classification model
│   │   ├── train_salary_model.py# Script training the salary estimation regressor model
│   │   ├── predict.py           # Loads models (local/S3) and runs inference
│   │   └── models/              # Gitignored folder holding trained binary (.joblib / .pkl) files
│   │
│   └── schemas/
│       ├── resume_schema.py     # Pydantic models validating upload payloads
│       └── result_schema.py     # Pydantic models validating analysis results
│
├── dashboard/
│   └── streamlit_app.py         # Streamlit frontend app showing dashboard & analytics
│
├── tests/
│   ├── test_pdf_parser.py       # Unit tests for text extraction validation
│   ├── test_embeddings.py       # Unit tests for vector shape and cosine similarity checks
│   └── test_api.py              # API route testing using TestClient
│
├── scripts/
│   └── seed_data.py             # Script to populate MongoDB with demo mock values
│
├── .env.example                 # Template for environment settings (secrets, DB URIs, S3 keys)
├── .gitignore                   # Version control exclusions
├── requirements.txt             # Python packages lists
├── Dockerfile                   # Deployment containerization configurations
├── docker-compose.yml           # Local cluster orchestration file (app, db, localstack, dashboard)
└── .github/workflows/ci.yml     # Continuous Integration pipeline setting up PyTest
```

---

## Data Pipeline Flow

1. **Ingestion & Storage**:
   - User uploads a resume PDF via the Streamlit frontend.
   - Streamlit calls the FastAPI endpoint `POST /upload-resume`.
   - FastAPI saves the metadata in MongoDB and uploads the raw PDF to AWS S3 (via Boto3).
   
2. **Analysis Pipeline**:
   - The user requests analysis via `POST /analyze`.
   - FastAPI retrieves the PDF from S3 and extracts raw text using the PDF parser.
   - Extracted text is normalized by the preprocessor.
   - Text is sent through the NLP Named Entity Recognition (spaCy) to extract skills, education, and experience entities.
   - Cleaned text is vectorized and matched against stored Job Descriptions using cosine similarity.
   - The profile features are fed into ML models to predict job role classification and salary regression bands.
   - The complete report is stored in MongoDB and returned to the client.

3. **Dashboard Reporting**:
   - Streamlit retrieves user uploads and pipeline histories using `GET /history/{user_id}` and renders interactive visualization charts.
