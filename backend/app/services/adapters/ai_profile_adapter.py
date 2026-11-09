import asyncio
import json
from typing import Any, Dict, List

import httpx

from app.config import settings
from app.schemas.profile import EducationItem, ExperienceItem, ProfileStructured, SocialLink
from app.services.errors import (
    AIResponseParseError,
    AIServiceTimeoutError,
    AIServiceUnavailableError,
)

try:
    from google import genai
except Exception:  # pragma: no cover - optional import fallback
    genai = None

GEMINI_MODEL = "gemini-2.5-flash"


PROMPT = """You are a resume parser.
Extract information from the resume text and return ONLY a valid JSON object.
Use exactly these keys:
- name: the candidate's full name as written at the top of the resume (string, empty if absent)
- socials: list of objects with keys label (e.g. LinkedIn, GitHub, Portfolio, LeetCode, Twitter) and url, taken only from links or handles that appear in the resume; never invent one
- skills: list of strings
- education: list of objects with keys degree, institution, year
- experience: list of objects with keys role, company, duration, summary
- interests: list of strings
Do not return markdown, code fences, or explanation text.
"""


class AIProfileAdapter:
    def __init__(self) -> None:
        self._preferred_provider = (settings.PROFILE_AI_PROVIDER or "groq").lower()
        self._gemini_client = None

        if settings.GEMINI_API_KEY and genai is not None:
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def structure(self, resume_text: str) -> ProfileStructured:
        text = resume_text[:20000]
        provider_order = self._provider_order()
        failures: List[str] = []

        for provider in provider_order:
            try:
                if provider == "groq":
                    raw = await self._call_groq(text)
                else:
                    raw = await self._call_gemini(text)

                payload = self._load_json_payload(raw)
                return self._normalize_payload(payload)
            except (AIServiceTimeoutError, AIServiceUnavailableError, AIResponseParseError) as exc:
                failures.append(f"{provider}: {exc}")

        if failures:
            raise AIServiceUnavailableError("; ".join(failures))

        raise AIServiceUnavailableError("No AI providers are configured")

    def _provider_order(self) -> List[str]:
        if self._preferred_provider == "gemini":
            return ["gemini", "groq"]
        return ["groq", "gemini"]

    async def _call_groq(self, text: str) -> str:
        if not settings.GROQ_API_KEY:
            raise AIServiceUnavailableError("GROQ_API_KEY is missing")

        body = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with asyncio.timeout(15):
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=body,
                    )
        except TimeoutError as exc:
            raise AIServiceTimeoutError("Groq request timed out") from exc
        except Exception as exc:
            raise AIServiceUnavailableError("Groq request failed") from exc

        if response.status_code >= 400:
            detail = response.text[:300]
            raise AIServiceUnavailableError(
                f"Groq request failed with {response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AIResponseParseError("Groq response is not valid JSON") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIResponseParseError("Groq response is missing content") from exc

    async def _call_gemini(self, text: str) -> str:
        if self._gemini_client is None:
            raise AIServiceUnavailableError("Gemini is not configured")

        try:
            async with asyncio.timeout(15):
                response = await self._gemini_client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=f"{PROMPT}\n\n{text}",
                )
        except TimeoutError as exc:
            raise AIServiceTimeoutError("Gemini request timed out") from exc
        except Exception as exc:
            raise AIServiceUnavailableError("Gemini request failed") from exc

        if not getattr(response, "text", None):
            raise AIResponseParseError("Gemini response is empty")

        return response.text

    def _load_json_payload(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIResponseParseError("AI response is not valid JSON") from exc

        if not isinstance(data, dict):
            raise AIResponseParseError("AI response root must be a JSON object")

        return data

    def _normalize_payload(self, data: Dict[str, Any]) -> ProfileStructured:
        skills = self._ensure_str_list(data.get("skills"))
        interests = self._ensure_str_list(data.get("interests"))

        education_raw = data.get("education")
        experience_raw = data.get("experience")

        education = [
            EducationItem(
                degree=str(item.get("degree", "")).strip(),
                institution=str(item.get("institution", "")).strip(),
                year=str(item.get("year", "")).strip(),
            )
            for item in self._ensure_dict_list(education_raw)
        ]

        experience = [
            ExperienceItem(
                role=str(item.get("role", "")).strip(),
                company=str(item.get("company", "")).strip(),
                duration=str(item.get("duration", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
            )
            for item in self._ensure_dict_list(experience_raw)
        ]

        socials: List[SocialLink] = []
        seen_urls: set[str] = set()
        for item in self._ensure_dict_list(data.get("socials")):
            url = str(item.get("url", "")).strip()
            if not url or url.lower().startswith(("javascript:", "data:")):
                continue
            if "@" in url and "://" not in url and not url.startswith("mailto:"):
                url = "mailto:" + url
            elif "://" not in url and not url.startswith("mailto:"):
                url = "https://" + url.lstrip("/")
            if url.lower() in seen_urls:
                continue
            seen_urls.add(url.lower())
            socials.append(SocialLink(label=str(item.get("label", "")).strip()[:40], url=url[:300]))

        return ProfileStructured(
            name=str(data.get("name") or "").strip()[:120],
            socials=socials[:10],
            skills=skills,
            education=education,
            experience=experience,
            interests=interests,
        )

    def _ensure_str_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []

        result: List[str] = []
        seen = set()
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _ensure_dict_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []

        result: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
        return result
