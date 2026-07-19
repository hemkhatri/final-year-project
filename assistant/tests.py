import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Product
from assistant.views import build_system_prompt

User = get_user_model()


class AssistantChatTestCase(TestCase):
    def setUp(self):
        # 1. Ensure GROQ credentials exist for configuration routing fallback safety
        if not hasattr(settings, 'GROQ_API_KEY'):
            settings.GROQ_API_KEY = 'mock_groq_key'

        # 2. Setup mock marketplace seller accounts
        self.seller = User.objects.create_user(
            username='ai_seller', 
            password='testpassword123', 
            role=User.Role.SELLER
        )

        # 3. Setup catalog entries that meet visibility constraints (available=True, stock > 0)
        self.category = Category.objects.create(name='Apparel', slug='apparel')
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Vintage Denim Jacket',
            slug='vintage-denim-jacket',
            price=Decimal('4500.00'),
            stock=15,
            available=True
        )

        self.chat_url = reverse('assistant_chat')

    def generate_mock_groq_response(self, content_str, status_code=200):
        """Helper to structure mock response blocks matching Groq's downstream schema."""
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        if status_code == 200:
            mock_resp.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content_str
                        }
                    }
                ]
            }
        else:
            mock_resp.text = "Internal Server Error Link Exception"
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("Mock HTTP Error")
        return mock_resp

    # ==========================================
    # PROMPT UTILITY TESTS
    # ==========================================

    def test_build_system_prompt_includes_active_products(self):
        """Ensure the system prompt automatically embeds serialized marketplace inventory strings."""
        prompt = build_system_prompt()
        self.assertIn("Vintage Denim Jacket", prompt)
        self.assertIn("4500.00", prompt)
        self.assertIn("Apparel", prompt)

    # ==========================================
    # VIEW PAYLOAD STRUCTURAL VALIDATION TESTS
    # ==========================================

    def test_chat_view_rejects_non_post_requests(self):
        """Ensure the view rejects non-POST request routes."""
        response = self.client.get(self.chat_url)
        self.assertEqual(response.status_code, 405)

    def test_chat_view_invalid_json_body(self):
        """Passing broken or raw string formats yields a bad request status."""
        response = self.client.post(
            self.chat_url, 
            data="not-json-payload-format", 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "Invalid JSON")

    def test_chat_view_missing_messages_array(self):
        """Payload missing structural conversation properties yields a validation alert."""
        payload = {"user_query": "Hello!"}
        response = self.client.post(
            self.chat_url, 
            data=json.dumps(payload), 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "A 'messages' array is required")

    # ==========================================
    # API RESPONSE & EXCEPTION HANDLING TESTS
    # ==========================================

    @patch('assistant.views.requests.post')
    def test_chat_view_successful_ai_handshake(self, mock_post):
        """Verifies clean parsing and pipeline tracking on valid downstream JSON schemas."""
        ai_reply_payload = {
            "message": "I found an excellent match for you!",
            "products": [
                {
                    "name": "Vintage Denim Jacket",
                    "price": "4500.00",
                    "category": "Apparel",
                    "link": "/product/vintage-denim-jacket/",
                    "image": None
                }
            ]
        }
        
        # Setup mock network response
        mock_post.return_value = self.generate_mock_groq_response(json.dumps(ai_reply_payload))

        client_messages = [{"role": "user", "content": "Looking for jackets"}]
        response = self.client.post(
            self.chat_url, 
            data=json.dumps({"messages": client_messages}), 
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], "I found an excellent match for you!")
        self.assertEqual(len(response.json()['products']), 1)
        self.assertEqual(response.json()['products'][0]['name'], "Vintage Denim Jacket")

    @patch('assistant.views.requests.post')
    def test_chat_view_handles_invalid_json_from_llm(self, mock_post):
        """If the LLM returns plain text instead of JSON, the view catches it and returns a 502."""
        mock_post.return_value = self.generate_mock_groq_response("Sorry, I cannot help with that (not structural json).")

        client_messages = [{"role": "user", "content": "Show items"}]
        response = self.client.post(
            self.chat_url, 
            data=json.dumps({"messages": client_messages}), 
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error'], "Assistant returned an unexpected format")

    @patch('assistant.views.requests.post')
    def test_chat_view_handles_remote_api_down_state(self, mock_post):
        """Network timeouts or bad API gateway endpoints return an availability fallback status."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection dropped out")

        client_messages = [{"role": "user", "content": "Hello assistant"}]
        response = self.client.post(
            self.chat_url, 
            data=json.dumps({"messages": client_messages}), 
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error'], "Assistant is currently unavailable")

    @patch('assistant.views.requests.post')
    def test_chat_view_handles_malformed_groq_response_schema(self, mock_post):
        """If the Groq response structure is missing choice/message arrays, catch it gracefully."""
        bad_structural_mock = MagicMock()
        bad_structural_mock.status_code = 200
        # Missing keys inside standard OpenAi completion block schemas
        bad_structural_mock.json.return_value = {"malformed_choices": []}
        
        mock_post.return_value = bad_structural_mock

        client_messages = [{"role": "user", "content": "Test item check"}]
        response = self.client.post(
            self.chat_url, 
            data=json.dumps({"messages": client_messages}), 
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error'], "Unexpected response from assistant")