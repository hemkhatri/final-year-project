# django_project/asgi.py
import os
from django.core.asgi import get_asgi_application

# Fix the path to point to django_project instead of final_year_project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            []
        )
    ),
})
