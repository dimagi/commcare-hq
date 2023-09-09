from rest_framework import serializers

from custom.abdm.const import (
    STATUS_EXPIRED,
    STATUS_GRANTED,
    STATUS_REVOKED,
    HealthInformationType,
)
from custom.abdm.serializers import (
    GatewayCareContextSerializer,
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayPurposeSerializer,
    GatewayRequestBaseSerializer,
)

HIP_GATEWAY_CONSENT_CHOICES = [(c, c) for c in [STATUS_GRANTED, STATUS_REVOKED, STATUS_EXPIRED]]


class GatewayConsentRequestNotifySerializer(GatewayRequestBaseSerializer):

    class GatewayNotificationSerializer(serializers.Serializer):

        class ConsentDetailSerializer(serializers.Serializer):
            schemaVersion = serializers.CharField(required=False)
            consentId = serializers.UUIDField()
            createdAt = serializers.DateTimeField()
            patient = GatewayIdSerializer()
            careContexts = serializers.ListField(child=GatewayCareContextSerializer(), min_length=1)
            purpose = GatewayPurposeSerializer()
            hip = GatewayIdSerializer()
            consentManager = GatewayIdSerializer()
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES),
                                            min_length=1)
            permission = GatewayPermissionSerializer()

        consentId = serializers.CharField()
        status = serializers.ChoiceField(choices=HIP_GATEWAY_CONSENT_CHOICES)
        consentDetail = ConsentDetailSerializer(required=False)
        signature = serializers.CharField()
        grantAcknowledgement = serializers.BooleanField()

    notification = GatewayNotificationSerializer()
