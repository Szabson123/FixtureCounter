from rest_framework import serializers

from .models import Counter, CounterSumFromLastMaint, Fixture


class FixtureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fixture
        fields = ['id', 'name', 'created_date']
    
    
class CounterSerializer(serializers.ModelSerializer):
    fixture = serializers.PrimaryKeyRelatedField(queryset=Fixture.objects.all(), write_only=True)
    
    class Meta:
        model = Counter
        fields = ['id', 'fixture', 'time_date']
    

class CounterFromLastMaintSerializer(serializers.ModelSerializer):
    fixture = serializers.PrimaryKeyRelatedField(queryset=Fixture.objects.all(), write_only=True)
    
    class Meta:
        model = CounterSumFromLastMaint
        fields = ['id', 'fixture']
