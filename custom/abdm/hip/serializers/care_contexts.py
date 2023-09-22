from rest_framework import serializers

from custom.abdm.const import HealthInformationType
from custom.abdm.serializers import (
    GatewayErrorSerializer,
    GatewayRequestBaseSerializer,
    GatewayResponseReferenceSerializer,
)


class LinkCareContextSerializer(serializers.Serializer):

    class PatientSerializer(serializers.Serializer):

        class CareContextSerializer(serializers.Serializer):
            referenceNumber = serializers.CharField()
            display = serializers.CharField()

        referenceNumber = serializers.CharField()
        display = serializers.CharField()
        careContexts = serializers.ListField(child=CareContextSerializer(), min_length=1)
        hiTypes = serializers.ListField(child=serializers.ChoiceField(
            choices=HealthInformationType.CHOICES), required=False)

    accessToken = serializers.CharField()
    hip_id = serializers.CharField()
    patient = PatientSerializer()


class GatewayOnAddContextsSerializer(GatewayRequestBaseSerializer):

    class AcknowledgementSerializer(serializers.Serializer):
        status = serializers.ChoiceField(choices=['SUCCESS'])

    acknowledgement = AcknowledgementSerializer(required=False, allow_null=True)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()
