from django.shortcuts import render, get_object_or_404
from django.db.models import OuterRef, Subquery, FileField
from rest_framework import viewsets, status, generics
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .serializers import SpeaCardSerializer, DiagnosisFileSerializer, SpeaCardLocationSerializer
from .models import SpeaCard, LocationSpea, DiagnosisFile
from .filters import SpeaCardFilter


class SpeaCardViewSet(viewsets.ModelViewSet):
    serializer_class = SpeaCardSerializer
    queryset = SpeaCard.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = SpeaCardFilter

    def get_queryset(self):

        latest_file = (
            DiagnosisFile.objects.filter(
                spea_card=OuterRef('pk'),
                active=True
            ).order_by('-created_at').values('file')[:1]
        )
        
        queryset = SpeaCard.objects.select_related('location').annotate(first_file=Subquery(latest_file))
        
        return queryset

    @action(detail=True, methods=['post'])
    def set_object_bad(self, request, *args, **kwargs):
        spea_card = self.get_object()

        if spea_card.is_broken:
            return Response({"error": "Spea Card is already broken"}, status=status.HTTP_400_BAD_REQUEST)
        
        spea_card.is_broken = True
        spea_card.save(update_fields=["is_broken"])

        return Response({"success": "Success"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def set_object_good(self, request, *args, **kwargs):
        spea_card = self.get_object()

        if not spea_card.is_broken:
            return Response({"error": "Spea Card is already good"}, status=status.HTTP_400_BAD_REQUEST)
        
        spea_card.is_broken = False
        spea_card.save(update_fields=["is_broken"])

        return Response({"success": "Success"}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], serializer_class=SpeaCardLocationSerializer)
    def change_place(self, request, *args, **kwargs):
        spea_card = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location_name = serializer.validated_data['name']

        location, _ = LocationSpea.objects.get_or_create(name=location_name)
        spea_card.location = location
        spea_card.save(update_fields=["location"])

        return Response({"success": "Success"}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def back_to_wardrobe(self, request, *args, **kwargs):
        spea_card = self.get_object()

        location = LocationSpea.objects.get(name="Szafa")

        spea_card.location = location
        spea_card.out_of_company = False
        spea_card.is_broken = False
        spea_card.save(update_fields=["location", "out_of_company", "is_broken"])

        return Response({"success": "Success"}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def send_out_of_company(self, request, *args, **kwargs):
        spea_card = self.get_object()

        spea_card.location = None
        spea_card.out_of_company = True

        spea_card.save(update_fields=["location", "out_of_company"])

        return Response({"success": "Success"}, status=status.HTTP_200_OK)
    
    #  47836
    

class CreateFileToBrokenCard(GenericAPIView):
    serializer_class = DiagnosisFileSerializer

    def post(self, request, *args, **kwargs):
        spea_card_id = self.kwargs.get('spea_card_id')
        spea_card = get_object_or_404(SpeaCard, pk=spea_card_id)

        if not spea_card.is_broken:
            return Response({"error": "Spea Card is good and you can't put diagnosic file"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save(spea_card=spea_card, active=True)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
