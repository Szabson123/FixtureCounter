from django.shortcuts import render, get_object_or_404

from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView

from .models import ProcessUnlinking, UserUnlinkerProfile, ProcessUnlinkingData
from .serializers import ProcessUnlinkingSerializer, UserUnlinkerProfileSerializer


class CreateUserLinkingProfile(CreateAPIView):
    serializer_class = UserUnlinkerProfileSerializer
    queryset = UserUnlinkerProfile.objects.all()

    def perform_create(self, serializer):
        user_card = serializer.validated_data['user_card']

        obj, created = UserUnlinkerProfile.objects.get_or_create(
            user_card = user_card
        )


class ProcessUnlinkingListView(ListAPIView):
    serializer_class = ProcessUnlinkingSerializer

    def get_queryset(self, *args, **kwargs):
        user_card_val = self.kwargs.get('user_card_id')
        user = get_object_or_404(UserUnlinkerProfile, user_card=user_card_val)

        return ProcessUnlinking.objects.filter(user=user).order_by('-time_date')