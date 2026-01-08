from django.urls import path
from .views import LoginAPIView, LogoutAPIView


urlpatterns = [
    path("auth/login/", LoginAPIView.as_view()),
    path("auth/logout/", LogoutAPIView.as_view()),
]