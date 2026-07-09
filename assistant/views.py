import json
import logging
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@require_POST
def chat_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user_message = data.get("message", "").strip()
    if not user_message:
        return JsonResponse({"error": "Message is required"}, status=400)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a helpful shopping assistant for an online marketplace."},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 500,
            },
            timeout=15,
        )
        logger.error("Groq status: %s, body: %s", response.status_code, response.text)  # <-- add this
        response.raise_for_status()
        result = response.json()
        reply = result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error("Groq request failed: %s", str(e))
        return JsonResponse({"error": "Assistant is currently unavailable"}, status=502)
    except (KeyError, IndexError):
        return JsonResponse({"error": "Unexpected response from assistant"}, status=502)

    return JsonResponse({"reply": reply})