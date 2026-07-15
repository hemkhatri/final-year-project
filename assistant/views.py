# assistant/views.py
import json
import logging
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .utils import get_available_products

logger = logging.getLogger(__name__)

def build_system_prompt():
    products = get_available_products()

    return f"""You are a shopping assistant for an online marketplace.

You can ONLY recommend products from this list (do not invent products or prices):
{json.dumps(products)}

RESPONSE FORMAT — you must respond with valid JSON only, no extra text, matching exactly this schema:
{{
  "message": "a short friendly reply to the user",
  "products": [
    {{
      "name": "string",
      "price": "string",
      "category": "string",
      "link": "string",
      "image": "string"
    }}
  ]
}}

Rules:
- Only include products that exist in the provided list above.
- If no matching product exists, return an empty "products" array and explain in "message".
- Do not include markdown, code fences, or any text outside the JSON object.
"""

@require_POST
def chat_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # 1. Accept an array of messages instead of a single string
    conversation_history = data.get("messages", [])
    if not conversation_history or not isinstance(conversation_history, list):
        return JsonResponse({"error": "A 'messages' array is required"}, status=400)

    # 2. Start with the system prompt, then append the user's history
    groq_messages = [{"role": "system", "content": build_system_prompt()}]
    
    for msg in conversation_history:
        if "role" in msg and "content" in msg:
            groq_messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": groq_messages,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        logger.error("Groq status: %s, body: %s", response.status_code, response.text)
        response.raise_for_status()
        result = response.json()
        raw_reply = result["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(raw_reply)
        except json.JSONDecodeError:
            logger.error("AI returned invalid JSON: %s", raw_reply)
            return JsonResponse({"error": "Assistant returned an unexpected format"}, status=502)

    except requests.exceptions.RequestException as e:
        logger.error("Groq request failed: %s", str(e))
        return JsonResponse({"error": "Assistant is currently unavailable"}, status=502)
    except (KeyError, IndexError):
        return JsonResponse({"error": "Unexpected response from assistant"}, status=502)

    return JsonResponse(parsed)