from django.contrib.auth import authenticate, login, logout
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"detail": "Username i password są wymagane"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response(
                {"detail": "Nieprawidłowe dane logowania"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)

        return Response(
            {
                "id": user.id,
                "username": user.username,
            }
        )


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request)
        return Response({"detail": "Wylogowano"})