try:
    from django.urls import path
    from .consumers import MessagingConsumer

    websocket_urlpatterns = [
        path('ws/messaging/', MessagingConsumer.as_asgi()),
    ]
except ModuleNotFoundError:  # pragma: no cover - fallback when channels isn't installed locally
    websocket_urlpatterns = []
