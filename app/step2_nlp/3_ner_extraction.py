"""
app/step2_nlp/3_ner_extractor.py — LLM-based NER Extractor

Uses Gemini to read resume text + job description and return
structured entities as JSON, instead of spaCy pattern matching.
"""

import os
import json
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])   # load your free API key from .env
model = genai.GenerativeModel("gemini-2.0-flash")         # pick the free, fast model


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
  software explicitly mentioned.

- education:
  Extract degrees, majors, universities/colleges, and educational qualifications.

- experience:
  Extract job titles, internships, companies, and work experience descriptions.

- projects:
  Extract project names and brief descriptions if available.

- certifications:
  Extract certifications, online courses, or professional credentials.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}
"""


def extract_entities(resume_text: str, job_description: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        job_description=job_description,
        resume_text=resume_text,
    )

    response = model.generate_content(prompt)          # send prompt to Gemini
    raw_output = response.text.strip()

    raw_output = raw_output.replace("```json", "").replace("```", "").strip()
    # ^ Gemini sometimes wraps JSON in markdown code fences — strip those off

    try:
        return json.loads(raw_output)                    # convert JSON text -> Python dict
    except json.JSONDecodeError:
        # LLM didn't return clean JSON — fail safely instead of crashing the pipeline
        return {
            "skills": [], "education": [], "experience": [],
            "projects": [], "certifications": [],
            "_error": "Failed to parse LLM output",
            "_raw": raw_output,
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