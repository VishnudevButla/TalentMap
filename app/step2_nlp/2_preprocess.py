"""
app/nlp/preprocess.py — Text Cleaning & Normalization

Takes raw extracted text from the PDF and cleans it before NER/embeddings.

Why preprocessing matters:
- Raw PDF text has noise: extra spaces, weird characters, broken lines
- NLP models perform significantly better on clean, normalized text
- Consistent formatting makes NER entity boundaries more accurate

Steps performed:
1. Lowercase the text (optional, depends on NER model needs)
2. Remove special characters, URLs, email addresses (or extract + store them)
3. Strip extra whitespace and newlines
4. Tokenization — split text into individual words/tokens
5. Remove stopwords — common words (the, a, is) that add no meaning
6. Lemmatization — reduce words to their base form (running → run)

Libraries:
- spaCy    → fast, handles tokenization + lemmatization + stopwords together
- NLTK     → more granular control, slightly more setup

Function:
  clean_text(raw_text: str) → str
  - Input: raw text from pdf_parser
  - Output: cleaned, normalized string ready for NER and embedding
"""

# import spacy

# nlp = spacy.load("en_core_web_sm")  # Load spaCy's English model

# def clean_text(raw_text: str) -> str:
#     # Step 1: Basic string cleaning (strip, lower, remove URLs)
#     # Step 2: Run through spaCy pipeline
#     # Step 3: Filter out stopwords and punctuation
#     # Step 4: Lemmatize each remaining token
#     # Step 5: Join tokens back into a clean string
#     pass
