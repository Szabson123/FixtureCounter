from django.shortcuts import render, get_object_or_404

from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework import status

from .models import ProcessUnlinking, UserUnlinkerProfile, ProcessUnlinkingData
from .serializers import ProcessUnlinkingSerializer, UserUnlinkerProfileSerializer, NoneSerializer


class CreateUserLinkingProfile(CreateAPIView):
    serializer_class = UserUnlinkerProfileSerializer
    queryset = UserUnlinkerProfile.objects.all()

    def perform_create(self, serializer):
        user_card = serializer.validated_data['user_card']

        obj, created = UserUnlinkerProfile.objects.get_or_create(
            user_card = user_card
        )


class LoginProfileUnlkiner(GenericAPIView):
    serializer_class = NoneSerializer
    queryset = UserUnlinkerProfile.objects.all()

    def post(self, request, *args, **kwargs):
        user_card_id = self.kwargs.get('user_card_id')
        try:
            user = UserUnlinkerProfile.objects.get(user_card=user_card_id)
        except:
            return Response({"error": "Profil doesn't esxists"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"success": "User is Valid"}, status=status.HTTP_200_OK)



class ProcessUnlinkingListView(ListAPIView):
    serializer_class = ProcessUnlinkingSerializer

    def get_queryset(self, *args, **kwargs):
        user_card_val = self.kwargs.get('user_card_id')
        user = get_object_or_404(UserUnlinkerProfile, user_card=user_card_val)

        return ProcessUnlinking.objects.filter(user=user).order_by('-time_date')