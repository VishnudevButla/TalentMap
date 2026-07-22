"""
app/nlp/embeddings.py — Resume/Job Description Vectorization and Similarity

This module is responsible for:
1. Converting resume and job description text into Sentence-BERT embeddings.
2. Computing cosine similarity between embeddings.
3. Computing weighted similarity across resume components.
"""

import logging
import time
from typing import Dict, Any
import numpy as np
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Load the Sentence-BERT model once when the module is imported.
# --------------------------------------------------------------------

MODEL_NAME = "all-MiniLM-L6-v2"
logger.info("Loading sentence-transformer model: %s", MODEL_NAME)
_model_load_start = time.perf_counter()
model = SentenceTransformer(MODEL_NAME)
logger.info(
    "Sentence-transformer model loaded in %.1fs", time.perf_counter() - _model_load_start
)


# --------------------------------------------------------------------
# Embedding Generation
# --------------------------------------------------------------------

def get_embedding(text: str) -> np.ndarray:
    """
    Generates a Sentence-BERT embedding for the given text.

    Args:
        text (str): Input text.

    Returns:
        np.ndarray: 384-dimensional embedding vector.
    """

    if not text or not text.strip():
        return np.array([])

    return model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )


# --------------------------------------------------------------------
# Cosine Similarity
# --------------------------------------------------------------------

def calculate_similarity(
    resume_vector: np.ndarray,
    job_vector: np.ndarray
) -> float:
    """
    Calculates cosine similarity between two embedding vectors.

    Args:
        resume_vector (np.ndarray): Resume embedding.
        job_vector (np.ndarray): Job description embedding.

    Returns:
        float: Similarity score between 0 and 1.
    """

    if resume_vector.size == 0 or job_vector.size == 0:
        return 0.0

    # Embeddings are normalized, so dot product == cosine similarity
    similarity = np.dot(resume_vector, job_vector)

    return float(similarity)


# --------------------------------------------------------------------
# Weighted Component Similarity
# --------------------------------------------------------------------

def calculate_weighted_component_similarity(
    resume_components: Dict[str, np.ndarray],
    job_components: Dict[str, np.ndarray],
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Calculates weighted similarity across resume components.

    Args:
        resume_components: Dictionary containing embeddings for
            skills, experience, projects, certifications.
        job_components: Same structure for the job description.
        weights: Weight assigned to each component.

    Returns:
        {
            "individual_scores": {...},
            "weighted_average_score": 84.32
        }
    """

    individual_scores = {}

    weighted_sum = 0.0
    total_weight = 0.0

    for component, weight in weights.items():

        resume_vector = resume_components.get(component)
        job_vector = job_components.get(component)

        if (
            resume_vector is None
            or job_vector is None
            or resume_vector.size == 0
            or job_vector.size == 0
        ):
            similarity = 0.0
        else:
            similarity = calculate_similarity(
                resume_vector,
                job_vector
            )

        individual_scores[component] = round(similarity, 4)

        weighted_sum += similarity * weight
        total_weight += weight

    final_score = (
        (weighted_sum / total_weight) * 100
        if total_weight > 0
        else 0.0
    )

    return {
        "individual_scores": individual_scores,
        "weighted_average_score": round(final_score, 2)
    }


# --------------------------------------------------------------------
# Convert extracted entities into embeddings
# --------------------------------------------------------------------

def embed_components(
    entities: Dict[str, Any]
) -> Dict[str, np.ndarray]:
    """
    Converts extracted resume/job entities into embeddings.

    Example input:
    {
        "skills": ["Python", "SQL"],
        "experience": ["Software Engineer"],
        "projects": ["Resume Parser"],
        "certifications": ["AWS CCP"]
    }

    Returns:
        Dictionary with embeddings for each component.
    """

    components = {}

    for key in [
        "skills",
        "experience",
        "projects",
        "certifications"
    ]:

        values = entities.get(key, [])

        if isinstance(values, list):
            text = " ".join(values)
        else:
            text = str(values)

        components[key] = get_embedding(text)

    logger.debug("Generated embeddings for components: %s", list(components.keys()))

    return components


# --------------------------------------------------------------------
# Default component weights
# --------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "skills": 0.40,
    "experience": 0.30,
    "projects": 0.20,
    "certifications": 0.10,
}