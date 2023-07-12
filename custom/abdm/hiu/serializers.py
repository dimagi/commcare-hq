import uuid
from datetime import datetime
from rest_framework import serializers

from custom.abdm.const import CONSENT_PURPOSES, HI_TYPES, DATA_ACCESS_MODES, TIME_UNITS
from custom.abdm.hiu.models import HIUConsentRequest


class HIUConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = HIUConsentRequest
        fields = '__all__'


class HIUConsentArtefactSerializer(serializers.ModelSerializer):
    class Meta:
        model = HIUConsentRequest
        fields = '__all__'


class RequestBaseSerializer(serializers.Serializer):
    requestId = serializers.UUIDField(default=uuid.uuid4())
    timestamp = serializers.DateTimeField(default=datetime.utcnow())


class ResponseSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class GenerateConsentSerializer(serializers.Serializer):
    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=CONSENT_PURPOSES)
        refUri = serializers.CharField(default='http://terminology.hl7.org/ValueSet/v3-PurposeOfUse')
        text = serializers.SerializerMethodField(method_name='get_code_text')

        def get_code_text(self, obj):
            return next(x[1] for x in CONSENT_PURPOSES if x[0] == obj['code'])

    class IdSerializer(serializers.Serializer):
        id = serializers.CharField()

    class CareContextSerializer(serializers.Serializer):
        patientReference = serializers.CharField()
        careContextReference = serializers.CharField()

    class RequesterSerializer(serializers.Serializer):

        class RequesterIdentifierSerializer(serializers.Serializer):
            type = serializers.CharField()
            value = serializers.CharField()
            system = serializers.CharField(required=False)

        name = serializers.CharField()
        identifier = RequesterIdentifierSerializer(required=False)

    class PermissionSerializer(serializers.Serializer):
        class DateRangeSerializer(serializers.Serializer):
            vars()['from'] = serializers.DateTimeField()
            to = serializers.DateTimeField()

        class FrequencySerializer(serializers.Serializer):
            unit = serializers.ChoiceField(choices=TIME_UNITS)
            value = serializers.IntegerField()
            repeats = serializers.IntegerField()

        accessMode = serializers.ChoiceField(choices=DATA_ACCESS_MODES)
        dateRange = DateRangeSerializer(required=False)
        dataEraseAt = serializers.DateTimeField()
        frequency = FrequencySerializer()

    purpose = PurposeSerializer()
    patient = IdSerializer(required=True)
    hip = IdSerializer(required=False)
    careContexts = serializers.ListField(required=False, child=CareContextSerializer(), min_length=1)
    hiu = IdSerializer(required=False)
    requester = RequesterSerializer()
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HI_TYPES), min_length=1)
    permission = PermissionSerializer()
