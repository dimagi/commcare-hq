from rest_framework import serializers

from custom.abdm.const import TIME_UNITS, DATA_ACCESS_MODES, GATEWAY_CONSENT_STATUS_CHOICES, CONSENT_PURPOSES


class GatewayRequestBaseSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class GatewayErrorSerializer(serializers.Serializer):
    code = serializers.IntegerField()
    message = serializers.CharField()


class GatewayResponseReferenceSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class GatewayIdSerializer(serializers.Serializer):
    id = serializers.CharField()


class GatewayCareContextSerializer(serializers.Serializer):
    patientReference = serializers.CharField()
    careContextReference = serializers.CharField()


class GatewayRequesterSerializer(serializers.Serializer):
    class IdentifierSerializer(serializers.Serializer):
        type = serializers.CharField()
        value = serializers.CharField()
        system = serializers.CharField(required=False, allow_null=True)

    name = serializers.CharField()
    identifier = IdentifierSerializer(required=False)


class GatewayPermissionSerializer(serializers.Serializer):
    class DateRangeSerializer(serializers.Serializer):
        vars()['from'] = serializers.DateTimeField()
        to = serializers.DateTimeField()

    class FrequencySerializer(serializers.Serializer):
        unit = serializers.ChoiceField(choices=TIME_UNITS)
        value = serializers.IntegerField()
        repeats = serializers.IntegerField()

    accessMode = serializers.ChoiceField(choices=DATA_ACCESS_MODES)
    dateRange = DateRangeSerializer()
    dataEraseAt = serializers.DateTimeField()
    frequency = FrequencySerializer()


class GatewayNotificationSerializer(serializers.Serializer):
    consentRequestId = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=GATEWAY_CONSENT_STATUS_CHOICES)
    consentArtefacts = serializers.ListField(required=False, child=GatewayIdSerializer())


class GatewayPurposeSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=CONSENT_PURPOSES)
    text = serializers.CharField()
    refUri = serializers.CharField(required=False)
