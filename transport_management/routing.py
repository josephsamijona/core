# transport_management/routing.py
from django.urls import re_path
from .consumers import TripStatusConsumer

websocket_urlpatterns = [
    re_path(r'ws/trip/(?P<trip_id>\d+)/$', TripStatusConsumer.as_asgi()),
]
