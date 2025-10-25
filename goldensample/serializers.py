from .models import *
from rest_framework import serializers
from .utils import gen_code
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404


User = get_user_model()

class GoldenCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounterOnGolden
        fields = ['id', 'golden_sample', 'counter']


class GoldenSampleCreateSerializer(serializers.Serializer):
    sn = serializers.CharField()
    type_golden = serializers.ChoiceField(choices=GoldenTypes)
    variant_code = serializers.CharField()
    variant_name = serializers.CharField(required=False, allow_blank=True)
    expire_date = serializers.DateField(required=False)
    

class GoldenSampleCheckSerializer(serializers.Serializer):
    goldens = serializers.ListField(
        child=serializers.CharField(), allow_empty=False
    )
    

class GroupMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupVariantCode
        fields = ['id', 'name']


class GoldenSampleSimpleSerializer(serializers.ModelSerializer):
    counter = serializers.SerializerMethodField()

    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'type_golden', 'expire_date', 'counter']

    def get_counter(self, obj):
        try:
            return obj.counterongolden.counter
        except:
            return None


class VariantFullSerializer(serializers.ModelSerializer):
    group = GroupMiniSerializer(read_only=True)
    goldens = GoldenSampleSimpleSerializer(source='goldensample_set', many=True)
    counter = serializers.IntegerField(read_only=True)

    class Meta:
        model = VariantCode
        fields = ['code', 'name', 'group', 'goldens', 'counter']


class VariantShortSerializer(serializers.ModelSerializer):
    golden_count = serializers.SerializerMethodField()

    class Meta:
        model = VariantCode
        fields = ['id', 'code', 'name', 'group', 'golden_count']

    def get_golden_count(self, obj):
        return obj.goldensample_set.count()
        
        
class GoldenSampleDetailedSerializer(serializers.ModelSerializer):
    counter = serializers.SerializerMethodField()
    variant = VariantShortSerializer()

    class Meta:
        model = GoldenSample
        fields = ['id', 'golden_code', 'expire_date', 'type_golden', 'counter', 'variant']

    def get_counter(self, obj):
        try:
            return obj.counterongolden.counter
        except:
            return None
        

class MapSampleSerailizer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'input', 'output']


class PcbEventSerializer(serializers.Serializer):
    group = serializers.CharField(required=False)
    events = serializers.DictField(
        child = serializers.BooleanField()
    )

    def create(self, validated_data):
        code = gen_code(8)
        events = validated_data["events"]
        objs = [
            PcbEvent(sn=sn, result=result, shared_plate=code)
            for sn, result in events.items()
        ]
        return PcbEvent.objects.bulk_create(objs)
    

class PcbEventSerializerCheck(serializers.Serializer):
    sn = serializers.CharField(required=True)


from .models import TimerGroup, CodeSmd, ClientName, ProcessName, TypeName, Department, MasterSample, EndCode


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']


class ClientNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientName
        fields = ['id', 'name']


class ProcessNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessName
        fields = ['id', 'name']


class TypeNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeName
        fields = ['id', 'name', 'color']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'color']


class CodeSmdSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeSmd
        fields = ['id', 'code']


class EndCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EndCode
        fields = ['id', 'code']


class MasterSampleSerializerList(serializers.ModelSerializer):
    client = ClientNameSerializer(read_only=True)
    process_name = ProcessNameSerializer(read_only=True)
    master_type = TypeNameSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    endcodes = EndCodeSerializer(many=True, read_only=True)
    code_smd = CodeSmdSerializer(read_only=True, many=True)
    departament = DepartmentSerializer(read_only=True)

    class Meta:
        model = MasterSample
        fields = [
            'id', 'project_name', 'sn', 'date_created', 'expire_date', 'pcb_rev_code',
            'client', 'process_name', 'master_type', 'created_by', 'endcodes', 'code_smd', 'departament'
        ]


class CodeSmdListField(serializers.ListField):
    child = serializers.CharField()

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("code_smd must be a list")

        if all(isinstance(item, int) for item in data):
            return {"mode": "id", "data": data}

        if all(isinstance(item, str) for item in data):
            return {"mode": "code", "data": data}

        raise serializers.ValidationError(
            "code_smd must be a list of integers (IDs) OR a list of strings (codes), not mixed."
        )


class MasterSampleManyCreateSerializer(serializers.ModelSerializer):
    samples = serializers.ListField(child=serializers.DictField(), write_only=True)
    code_smd = CodeSmdListField(required=False)
    endcodes = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = MasterSample
        fields = [
            "client", "process_name", "created_by", "departament",
            "project_name", "expire_date", "pcb_rev_code",
            "code_smd", "endcodes", "samples",
        ]

    def create(self, validated_data):
        code_smd_data = validated_data.pop("code_smd", None)
        endcodes_data = validated_data.pop("endcodes", [])
        samples_data = validated_data.pop("samples", [])

        created_objects = []

        for sample in samples_data:
            sn = sample.get("sn")
            master_type_id = sample.get("master_type")
            details_text = sample.get("details", "")

            master_type = get_object_or_404(TypeName, pk=master_type_id)

            master = MasterSample.objects.create(
                **validated_data,
                sn=sn,
                master_type=master_type,
                details=details_text,
            )

            if code_smd_data:
                mode = code_smd_data["mode"]
                items = code_smd_data["data"]
                smd_instances = []
                if mode == "id":
                    smd_instances = list(CodeSmd.objects.filter(pk__in=items))
                elif mode == "code":
                    for code in items:
                        obj, _ = CodeSmd.objects.get_or_create(code=code)
                        smd_instances.append(obj)
                master.code_smd.set(smd_instances)

            if endcodes_data:
                endcode_instances = []
                for code in endcodes_data:
                    obj, _ = EndCode.objects.get_or_create(code=code)
                    endcode_instances.append(obj)
                master.endcodes.set(endcode_instances)

            created_objects.append(master)

        return created_objects


class MasterSampleUpdateSerializer(serializers.ModelSerializer):
    code_smd = serializers.SerializerMethodField()
    endcodes = serializers.SerializerMethodField()

    class Meta:
        model = MasterSample
        fields = [
            "id",
            "client", "process_name", "master_type", "created_by", "departament",
            "details", "comennt",
            "project_name", "sn",
            "expire_date", "pcb_rev_code",
            "code_smd", "endcodes",
        ]
        extra_kwargs = {f: {"required": False, "allow_null": True} for f in fields}

    def get_code_smd(self, instance):
        return list(instance.code_smd.values_list("code", flat=True))

    def get_endcodes(self, instance):
        return list(instance.endcodes.values_list("code", flat=True))

    def update(self, instance, validated_data):
        code_smd_list = self.initial_data.get("code_smd", None)
        endcode_list = self.initial_data.get("endcodes", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        # Obsługa M2M
        from .models import CodeSmd, EndCode

        if isinstance(code_smd_list, list):
            smd_objs = [CodeSmd.objects.get_or_create(code=c)[0] for c in code_smd_list]
            instance.code_smd.set(smd_objs)

        if isinstance(endcode_list, list):
            end_objs = [EndCode.objects.get_or_create(code=c)[0] for c in endcode_list]
            instance.endcodes.set(end_objs)

        return instance


class MachineTimeStampSerializer(serializers.Serializer):
    machine_name = serializers.CharField(required=True, error_messages={
        "required": "You need to provide machine_name",
        "blank": "You need provide machine_name"
    })