from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

class PasswordProtectedMixin:
    def check_password(self, request):
        input_password = request.data.get('password') or request.query_params.get('password')
        if input_password != settings.VARIANT_SECRET_PASSWORD:
            return Response({'error': 'Nieprawidłowe hasło'}, status=status.HTTP_403_FORBIDDEN)
        return None