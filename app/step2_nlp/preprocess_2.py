"""
app/nlp/preprocess.py — Text Cleaning & Normalization

Takes raw extracted text from the PDF and cleans it before NER/embeddings.
"""

import re
import spacy

nlp = spacy.load("en_core_web_sm")  # Load spaCy's English model

URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s\-\(\)]{7,}\d")


def extract_contact_info(raw_text: str) -> dict:
    """Pull out URLs, emails, and phone numbers before they get stripped."""
    return {
        "emails": EMAIL_RE.findall(raw_text),
        "urls": URL_RE.findall(raw_text),
        "phones": PHONE_RE.findall(raw_text),
    }


def _basic_clean(raw_text: str) -> str:
    """Strip URLs/emails, collapse whitespace. Keeps case and punctuation
    intact since spaCy's tokenizer/NER work better on natural text."""
    text = URL_RE.sub(" ", raw_text)
    text = EMAIL_RE.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def clean_text(raw_text: str) -> str:
    """
    Clean and normalize text for embeddings/downstream matching.

    Note: this lowercases + lemmatizes + drops stopwords, which is fine
    for embeddings/keyword matching, but you generally do NOT want to
    run NER on this output — NER models rely on casing and punctuation
    to find entity boundaries (e.g. "Google" vs "google"). Run NER on
    the raw or lightly-cleaned text instead (see `clean_text_for_ner`
    below), and use `clean_text` only for the embedding/matching step.
    """
    if not raw_text:
        return ""

    text = _basic_clean(raw_text)
    doc = nlp(text)

    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and not token.is_space
        and token.lemma_.strip()
    ]

    return " ".join(tokens)


def clean_text_for_ner(raw_text: str) -> str:
    """
    Lighter cleaning pass that preserves case, punctuation, and word
    order — use this version as input to your NER step instead of
    `clean_text`.
    """
    return _basic_clean(raw_text)