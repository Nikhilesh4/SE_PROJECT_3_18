"""
Profile Service — Resume parsing pipeline.

1. extract_text_from_pdf  → PyMuPDF (fitz) to pull raw text from a PDF
2. parse_resume_with_gemini → Gemini API to convert raw text into structured JSON
"""

import json
import re
from typing import Optional

import fitz  # PyMuPDF
import google.generativeai as genai

from app.config import settings

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Open an in-memory PDF and return all text concatenated page-by-page."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# Gemini resume parsing
# ---------------------------------------------------------------------------

_GEMINI_PROMPT = """\
You are a resume-parsing assistant.  Given the raw text extracted from a
student's PDF resume, return **only** a JSON object (no markdown fences, no
explanation) with exactly these keys:

{
  "skills": ["skill1", "skill2", ...],
  "education": "A brief summary of education history",
  "experience": "A brief summary of work / project experience",
  "interests": ["interest1", "interest2", ...]
}

Rules:
- "skills" should be a flat list of technical and soft skills you can identify.
- "education" should summarise degrees, institutions, and years.
- "experience" should summarise jobs, internships, and notable projects.
- "interests" should be inferred career/academic interests based on the resume.
- Return ONLY the JSON object.  No extra text.

--- BEGIN RESUME TEXT ---
{resume_text}
--- END RESUME TEXT ---
"""


def _extract_json(text: str) -> dict:
    """
    Best-effort extraction of the first JSON object from Gemini's response.
    Handles cases where the model wraps the JSON in markdown code fences.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: find first { ... } block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse JSON from Gemini response")


def parse_resume_with_gemini(raw_text: str) -> dict:
    """
    Send extracted resume text to the Gemini API and return parsed profile data.

    Returns dict with keys: skills, education, experience, interests
    """
    if settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("your-"):
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            prompt = _GEMINI_PROMPT.replace("{resume_text}", raw_text[:8000])
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
            )
            parsed = _extract_json(chat_completion.choices[0].message.content)
            return {
                "skills": parsed.get("skills", []),
                "education": parsed.get("education", ""),
                "experience": parsed.get("experience", ""),
                "interests": parsed.get("interests", []),
            }
        except ImportError:
            pass # groq not installed, fallback to gemini
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                fallback_reason = "Groq API rate limited. Please try again later."
            else:
                fallback_reason = f"Groq API Error: {error_msg}"
            return _mock_parse(raw_text, fallback_reason)

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your-"):
        # Fallback mock mode for development without a real API key
        return _mock_parse(raw_text)

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = _GEMINI_PROMPT.replace("{resume_text}", raw_text[:8000])  # cap length
    try:
        response = model.generate_content(prompt)
        parsed = _extract_json(response.text)
    except Exception as e:
        # Gemini API error (rate-limit, network, etc.) — fall back to mock
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            fallback_reason = "Gemini API Free Tier quota exceeded or rate limited. Please try again later."
        else:
            fallback_reason = f"Gemini API Error: {error_msg}"
        return _mock_parse(raw_text, fallback_reason)

    # Normalise keys
    return {
        "skills": parsed.get("skills", []),
        "education": parsed.get("education", ""),
        "experience": parsed.get("experience", ""),
        "interests": parsed.get("interests", []),
    }


# ---------------------------------------------------------------------------
# Fallback mock parser (used when no Gemini key is configured)
# ---------------------------------------------------------------------------


def _mock_parse(raw_text: str, reason: str = "(Gemini API key not configured — set GEMINI_API_KEY in .env)") -> dict:
    """Naive keyword extraction so the app works without a Gemini key or on rate limits."""
    # Common tech keywords to look for
    tech_keywords = [
        "python", "java", "javascript", "typescript", "react", "next.js",
        "node.js", "sql", "postgresql", "mongodb", "docker", "kubernetes",
        "aws", "git", "linux", "html", "css", "c++", "c#", "rust", "go",
        "machine learning", "deep learning", "data science", "flask",
        "django", "fastapi", "tensorflow", "pytorch",
    ]
    lower = raw_text.lower()
    found_skills = [kw for kw in tech_keywords if kw in lower]

    return {
        "skills": found_skills if found_skills else ["(AI parsing failed)"],
        "education": reason,
        "experience": reason,
        "interests": [],
    }
