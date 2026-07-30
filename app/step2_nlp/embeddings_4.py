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
# Load the BGE embedding model once when the module is imported.
# --------------------------------------------------------------------

MODEL_NAME = "BAAI/bge-base-en-v1.5"
logger.info("Loading sentence-transformer model: %s", MODEL_NAME)
_model_load_start = time.perf_counter()
model = SentenceTransformer(MODEL_NAME)
logger.info(
    "Sentence-transformer model loaded in %.1fs", time.perf_counter() - _model_load_start
)

# BGE models recommend a query instruction prefix for asymmetric search
# (e.g. short query text vs. longer passage text). Since job descriptions
# often act as the "query" being matched against resume "passages", this
# prefix is applied optionally via the `is_query` flag in get_embedding().
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# --------------------------------------------------------------------
# Embedding Generation
# --------------------------------------------------------------------

def get_embedding(text: str, is_query: bool = False) -> np.ndarray:
    """
    Generates a BGE embedding for the given text.

    Args:
        text (str): Input text.
        is_query (bool): If True, prepends the BGE query instruction
            prefix. Use this for job description text when comparing
            against resume text. Leave False for resume/passage text.

    Returns:
        np.ndarray: 768-dimensional embedding vector.
    """

    if not text or not text.strip():
        return np.array([])

    if is_query:
        text = BGE_QUERY_PREFIX + text

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
    Calculates weighted similarity across resume/job components, comparing
    only the components that actually exist on BOTH sides.

    A component missing on either side (no text was ever extracted for it)
    is excluded from the average entirely — its weight is NOT counted in
    the denominator — rather than being scored 0.0 while still counting at
    full weight. The old behavior meant "no data" and "compared and did
    not match" were indistinguishable and produced the same penalty; a job
    missing one 40%-weighted component could never score above 60% no
    matter how well everything else fit. individual_scores reports None
    (not 0.0) for an excluded component, so a caller/UI can tell "absent"
    from "compared, low similarity" apart.

    Args:
        resume_components: Dictionary containing embeddings for
            skills, experience, education, certifications.
        job_components: Same structure for the job.
        weights: Weight assigned to each component.

    Returns:
        {
            "individual_scores": {"skills": 0.82, "education": None, ...},
            "weighted_average_score": 84.32 or None if nothing was comparable
        }
    """

    individual_scores = {}

    weighted_sum = 0.0
    total_weight = 0.0

    for component, weight in weights.items():

        resume_vector = resume_components.get(component)
        job_vector = job_components.get(component)

        resume_has_data = resume_vector is not None and resume_vector.size > 0
        job_has_data = job_vector is not None and job_vector.size > 0

        if not (resume_has_data and job_has_data):
            individual_scores[component] = None
            continue

        similarity = calculate_similarity(resume_vector, job_vector)
        individual_scores[component] = round(similarity, 4)

        weighted_sum += similarity * weight
        total_weight += weight

    final_score = (
        round((weighted_sum / total_weight) * 100, 2)
        if total_weight > 0
        else None
    )

    return {
        "individual_scores": individual_scores,
        "weighted_average_score": final_score,
    }


# --------------------------------------------------------------------
# Convert extracted entities into embeddings
# --------------------------------------------------------------------

def embed_components(
    entities: Dict[str, Any],
    is_query: bool = False
) -> Dict[str, np.ndarray]:
    """
    Converts extracted resume/job entities into embeddings.

    Example input:
    {
        "skills": ["Python", "SQL"],
        "experience": ["Software Engineer"],
        "education": ["B.S. Computer Science"],
        "certifications": ["AWS CCP"]
    }

    Args:
        entities: Extracted component text lists.
        is_query: Pass True when embedding job description components,
            False when embedding resume components.

    Returns:
        Dictionary with embeddings for each component.
    """

    components = {}

    for key in [
        "skills",
        "experience",
        "education",
        "certifications"
    ]:

        values = entities.get(key, [])

        if isinstance(values, list):
            text = " ".join(values)
        else:
            text = str(values)

        components[key] = get_embedding(text, is_query=is_query)

    logger.debug("Generated embeddings for components: %s", list(components.keys()))

    return components


# --------------------------------------------------------------------
# Default component weights
# --------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "skills": 0.40,
    "experience": 0.30,
    "education": 0.15,
    "certifications": 0.15,
}
# "projects" was dropped — a job posting has no structural equivalent to a
# resume's personal projects, so that component was always comparing a
# resume's real project text against the same raw job description reused
# for every other component (see job_entity_extractor.py's docstring).
# Under the honest-missing-data scoring above, an always-absent component
# would just never contribute anyway; removing it here is the same
# outcome without carrying dead weight in the config.