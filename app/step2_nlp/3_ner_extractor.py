"""
app/nlp/ner_extractor.py — Named Entity Recognition (NER) Extractor

This module is responsible for identifying and extracting entities from the clean resume text,
specifically targeting:
1. Skills (e.g., Python, AWS, SQL, Machine Learning)
2. Education (e.g., Bachelor of Science, Stanford University)
3. Experience / Roles (e.g., Software Engineer, Data Scientist, Product Manager)
4. Projects (e.g., e-commerce recommendation system, personal blog)
5. Certifications (e.g., AWS Certified Solutions Architect, PMP)

We use spaCy's pre-trained models or custom-trained EntityRuler/pipelines.

Flow:
1. Load spaCy model (e.g., "en_core_web_sm" or a custom trained pipeline).
2. Add custom rules via EntityRuler or load custom NER pipeline for resume entities.
3. Process clean resume text.
4. Extract entities, format them, and return a structured dictionary.
"""

import spacy
from typing import Dict, List, Any

class ResumeNERExtractor:
    """
    Handles Named Entity Recognition tasks on resume text.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initializes the spaCy language model and configures custom entity rulers if needed.
        
        Args:
            model_name (str): Name of the spaCy pipeline model to load.
        """
        # 1. Load the spaCy model.
        # 2. Check if a custom EntityRuler is needed for matching specific keywords (e.g., custom skills dictionary).
        # 3. Add EntityRuler to spaCy pipeline.
        pass

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Processes text and extracts key entities (Skills, Education, Experience, Projects, Certifications).
        
        Args:
            text (str): Cleaned, normalized resume text.
            
        Returns:
            Dict[str, List[str]]: A dictionary of extracted entities, e.g.:
                {
                    "skills": ["python", "fastapi", "docker"],
                    "education": ["Bachelor of Science in Computer Science"],
                    "experience": ["Senior Software Engineer"],
                    "projects": ["personal portfolio website"],
                    "certifications": ["AWS Certified Solutions Architect"]
                }
        """
        # 1. Process text through spaCy NLP pipeline: doc = self.nlp(text)
        # 2. Loop over doc.ents (entities detected).
        # 3. Classify entities based on their label (e.g., ORG, GPE, or custom labels like SKILL, EDU, PROJ, CERT).
        # 4. Deduplicate and clean entity lists.
        # 5. Return dict.
        return {
            "skills": [],
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": []
        }
