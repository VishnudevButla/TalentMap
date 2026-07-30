"""
app/step2_nlp/3_ner_extractor.py — LLM-based NER Extractor

Uses Groq (OpenAI-compatible chat completions API, hosting open models
like Llama) to read resume text + job description and return structured
entities as JSON, instead of spaCy pattern matching. Previously used
Gemini directly — switched because the Gemini free tier required a
billing-enabled project to grant any quota at all (limit: 0 on every
account tried), while Groq's free tier actually works for this use case.
Plain `requests` against Groq's REST endpoint, no new SDK dependency —
matches how job_source_fetcher.py already calls Adzuna/RemoteOK.
"""

import os
import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

# Load .env so GROQ_API_KEY is available even when not set in the shell
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_api_key() -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to your .env file to enable "
            "LLM-based NER extraction."
        )
    return api_key


PROMPT_TEMPLATE = """
You are an expert Resume Information Extraction System.

Your task is to extract structured information from the RESUME.
The JOB DESCRIPTION is provided only for context to help identify relevant terms.

IMPORTANT RULES:
1. Extract ONLY information explicitly present in the RESUME.
2. Do NOT infer, guess, or generate information.
3. Do NOT use information from the JOB DESCRIPTION in the output.
4. Return ONLY valid JSON.
5. Do NOT include markdown, explanations, or any extra text.
6. Every key must always exist.
7. Use empty arrays ([]) if no information is found.
8. EVERY array below must contain PLAIN STRINGS ONLY — never objects,
   never nested fields. Each entry is one self-contained human-readable
   line of text, not a structured record.

Return JSON in EXACTLY this format:

{
  "skills": [],
  "education": [],
  "experience": [],
  "projects": [],
  "certifications": []
}

Extraction Guidelines:

- skills:
  Extract technical skills, programming languages, frameworks, libraries,
  databases, cloud platforms, developer tools, operating systems, and
  software explicitly mentioned. One skill per string, e.g. "Python".

- education:
  One string per degree, combining degree, major, and institution, e.g.
  "B.S. Computer Science, State University, 2019" — not separate fields.

- experience:
  One string per role, combining job title, company, and a short
  description, e.g. "Senior Backend Engineer at TechCorp (2021-2024) —
  built REST APIs serving 1M+ requests/day" — not separate fields.

- projects:
  One string per project, combining its name and a brief description,
  e.g. "Real-time chat application — built with WebSockets and Redis".

- certifications:
  Extract certifications, online courses, or professional credentials.
  One certification per string.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}
"""


def _flatten_entities(parsed: dict) -> dict:
    """
    Defensive safety net: the prompt requires plain strings, but LLMs don't
    always comply — coerce any stray objects/lists per entry into a single
    readable string so this can never violate NERResult's List[str] schema
    downstream, no matter what the model actually returned.
    """
    def _to_str(item):
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return ", ".join(str(v) for v in item.values() if v)
        return str(item)

    flattened = {}
    for key in ("skills", "education", "experience", "projects", "certifications"):
        items = parsed.get(key) or []
        if not isinstance(items, list):
            items = [items]
        flattened[key] = [_to_str(item) for item in items if item]
    return flattened


def extract_entities(resume_text: str, job_description: str) -> dict:
    _empty = {
        "skills": [], "education": [], "experience": [],
        "projects": [], "certifications": [],
    }

    try:
        api_key = _get_api_key()
    except EnvironmentError as exc:
        logger.warning("NER skipped: %s", exc)
        return _empty

    # Never log `prompt` — it embeds the full resume/JD text.
    # .replace(), not .format() — the template's JSON example block
    # contains literal {braces} that .format() misreads as placeholders.
    prompt = PROMPT_TEMPLATE.replace("{job_description}", job_description) \
                             .replace("{resume_text}", resume_text)

    try:
        start = time.perf_counter()
        response = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        duration = time.perf_counter() - start
        logger.info("Groq entity extraction completed in %.1f seconds", duration)

        raw_output = response.json()["choices"][0]["message"]["content"].strip()
        raw_output = raw_output.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_output)            # convert JSON text → Python dict
        return _flatten_entities(parsed)
    except Exception as exc:
        # LLM didn't return clean JSON or network error — fail safely,
        # same fallback behavior as before, now with a full traceback logged.
        logger.exception("NER extraction failed")
        return {
            **_empty,
            "_error": str(exc),
        }
'''
# Example Usage (for testing)
if __name__ == "__main__":
    # Sample data for testing
    sample_resume = """
    John Doe
    123 Main St, Anytown, USA | (123) 456-7890 | [EMAIL_ADDRESS]
    linkedin.com/in/johndoe | github.com/johndoe

    Summary
    Highly motivated Computer Science student with strong programming skills in Python,
    Java, and C++. Experienced in developing web applications and machine learning models.

    Education
    Bachelor of Science in Computer Science, Anytown University
    GPA: 3.8/4.0 | Expected Graduation: May 2025

    Skills
    Programming Languages: Python, Java, C++, JavaScript, SQL
    Frameworks & Libraries: React, Node.js, Django, TensorFlow, PyTorch
    Tools & Platforms: Git, Docker, AWS, MongoDB, MySQL
    Concepts: Object-Oriented Programming, Data Structures, Algorithms, Machine Learning

    Projects
    E-Commerce Website
    Developed a full-stack e-commerce platform using React, Node.js, and MongoDB.
    Features: user authentication, product catalog, shopping cart, payment integration.
    
    Sentiment Analysis Model
    Built a machine learning model to analyze customer reviews with 90% accuracy using
    TensorFlow and NLTK.

    Certifications
    AWS Certified Cloud Practitioner | Issued: March 2024
    Python for Data Science Certificate | Coursera | Issued: July 2023
    """

    sample_job_description = """
    Senior Full Stack Developer
    We are looking for an experienced Full Stack Developer to join our team.
    Responsibilities: 
    - Design and develop web applications
    - Work with technologies like React, Node.js, Python, and MongoDB
    - Implement machine learning features
    Qualifications: 
    - Bachelor's degree in Computer Science or related field
    - 3+ years of experience
    - Strong programming skills in Python, JavaScript
    - Experience with AWS and databases
    """

    print("--- Running Resume Information Extraction ---")
    entities = extract_entities(sample_resume, sample_job_description)
    print("\n--- Extracted Information ---")
    print(json.dumps(entities, indent=2))

    # Test error handling
    print("\n--- Testing Error Handling ---")
    error_entities = extract_entities("Invalid JSON data", sample_job_description)
    # print(json.dumps(error_entities, indent=2))'''