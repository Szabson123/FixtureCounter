from rest_framework import serializers
from .models import Counter, CounterSumFromLastMaint, Fixture, Machine


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


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ['id', 'machine_id', 'machine_name']
        
        
class FullInfoFixtureSerializer(serializers.ModelSerializer):
    counter_all = serializers.FloatField(source='counter_all_value', read_only=True)
    counter_last_maint = serializers.FloatField(source='counter_last_maint_value', read_only=True)
    last_maint_date = serializers.DateTimeField(read_only=True)
    limit_procent = serializers.SerializerMethodField()

    class Meta:
        model = Fixture
        fields = ['id', 'name', 'counter_all', 'counter_last_maint', 'last_maint_date', 'limit_procent']

    def get_limit_procent(self, obj):
        if obj.limit_procent is not None:
            return round(obj.limit_procent, 2)
        return None