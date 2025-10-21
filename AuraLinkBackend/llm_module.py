# llm_module.py
"""
Lightweight LLM utilities for AuraLink.

This file avoids importing langchain and instead uses the `openai` package directly.
It reads API keys from environment variables (.env via python-dotenv) and provides two functions:

- generate_quote(temp, hum) -> str
- summarize_email(email_text) -> (summary_str, urgency_str)
"""

from dotenv import load_dotenv
import os
from openai import OpenAI
import time
import random

load_dotenv()

# ------------------- Configuration -------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = OpenAI()

MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds
COOLDOWN_SECONDS = int(os.getenv("OPENAI_COOLDOWN_SECONDS", 600))  # default 10 minutes
_cooldown_until = 0

# ------------------- Chat Model Call -------------------
def _call_chat_model(prompt, temperature=0.7, max_tokens=256):
    global _cooldown_until

    if time.time() < _cooldown_until:
        raise RuntimeError("OpenAI API is in cooldown due to previous quota errors")

    if not OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key not configured in environment")

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            message = getattr(choice, "message", None) or getattr(choice, "message", None) \
                      or (choice.get("message") if hasattr(choice, 'get') else None)
            if isinstance(message, dict):
                return message.get("content", "").strip()
            return getattr(message, "content", str(message)).strip()
        except Exception as e:
            last_exc = e
            s = str(e)
            if "insufficient_quota" in s or ("quota" in s and ("429" in s or "insufficient" in s)):
                print(f"[LLM API] Quota detected — entering cooldown for {COOLDOWN_SECONDS}s: {e}")
                _cooldown_until = time.time() + COOLDOWN_SECONDS
                raise
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                print(f"[LLM API] transient error (attempt {attempt}/{MAX_RETRIES}), retrying in {backoff:.1f}s: {e}")
                time.sleep(backoff)
                continue
            raise last_exc

# ------------------- Generate Quote -------------------
def generate_quote(temp, hum):
    prompt = (
        f"Generate a short literature-style quote inspired by an indoor environment "
        f"where the temperature is {temp}°C and humidity is {hum}%. Make it poetic, under 30 words."
    )
    try:
        return _call_chat_model(prompt, temperature=0.7, max_tokens=80)
    except Exception as e:
        print(f"[LLM Quote Error] {e}")
        return f"A quiet room at {temp}°C, {hum}%—breath of stillness."

# ------------------- Summarize Email & Detect Urgency -------------------
def summarize_email(email_text):
    """
    Summarize the email and return (summary, urgency)
    Urgency is one of: "High", "Moderate", "Low"
    """

    text_lower = (email_text or "").lower()

    # --- 1. Keyword-based heuristic (instant detection) ---
    high_keywords = [
        "urgent", "immediately", "asap", "as soon as possible",
        "critical", "deadline today", "error", "important",
        "alert", "emergency", "attention required"
    ]
    moderate_keywords = [
        "soon", "reminder", "deadline", "submit", "by tomorrow",
        "check", "review", "respond", "this week", "by friday"
    ]

    urgency = "Low"
    if any(k in text_lower for k in high_keywords):
        urgency = "High"
    elif any(k in text_lower for k in moderate_keywords):
        urgency = "Moderate"

    # --- 2. Fallback to LLM for robust summary & urgency detection ---
    prompt = (
        "Summarize this email in one short sentence and rate its urgency as Low, Moderate, or High:\n\n"
        + (email_text or "")
    )

    try:
        response = _call_chat_model(prompt, temperature=0.0, max_tokens=120)
        resp_upper = (response or "").upper()
        if "HIGH" in resp_upper:
            urgency = "High"
        elif "MODERATE" in resp_upper:
            urgency = "Moderate"
        elif "LOW" in resp_upper:
            urgency = "Low"

        summary = response.split('\n')[0].strip()
        if not summary:
            summary = (email_text or "").split('\n')[0].strip()[:140]

    except Exception as e:
        print(f"[LLM Email Error] {e}")
        summary = (email_text or "").split('\n')[0].strip()[:140]

    return summary, urgency
