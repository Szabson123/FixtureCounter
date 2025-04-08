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
    counter_all = serializers.IntegerField(source='counter_all.counter', read_only=True)
    counter_last_maint = serializers.IntegerField(source='counter_last_maint.counter', read_only=True)
    last_maint_date = serializers.SerializerMethodField()
    limit_procent = serializers.SerializerMethodField()

    class Meta:
        model = Fixture
        fields = ['id', 'name', 'counter_all', 'counter_last_maint', 'last_maint_date', 'limit_procent']

    def get_last_maint_date(self, obj):
        last_counter = obj.backup.order_by('-date').first()
        return last_counter.date if last_counter else None
    
    def get_limit_procent(self, obj):
        counter_value = getattr(obj.counter_last_maint, 'counter', None)
        if counter_value is not None and counter_value != 0:
            return round((counter_value / obj.cycles_limit) * 100, 2)
        return None
    