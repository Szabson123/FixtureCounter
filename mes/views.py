from django.shortcuts import render
from .serializers import UnlockHistorySerializer
from rest_framework.generics import ListAPIView
from .models import UnlockHistory

class UnlockHistoryView(ListAPIView):
    serializer_class = UnlockHistorySerializer
    queryset = UnlockHistory.objects.all().order_by('-date_time')

# Create your views here.
