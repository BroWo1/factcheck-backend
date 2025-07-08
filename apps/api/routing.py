from django.urls import path
from apps.api.consumers import FactCheckConsumer

websocket_urlpatterns = [
    path('ws/fact-check/<uuid:session_id>/', FactCheckConsumer.as_asgi()),
]
