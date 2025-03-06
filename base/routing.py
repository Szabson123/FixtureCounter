from django.urls import re_path
from .consumers import FixtureConsumer

websocket_urlpatterns = [
    re_path(r'ws/fixtures/$', FixtureConsumer.as_asgi()),
]