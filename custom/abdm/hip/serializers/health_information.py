from rest_framework import serializers

from custom.abdm.serializers import (
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayRequestBaseSerializer,
    KeyMaterialSerializer,
)


class GatewayHealthInformationRequestSerializer(GatewayRequestBaseSerializer):

    class HIRequestSerializer(serializers.Serializer):
        consent = GatewayIdSerializer()
        dateRange = GatewayPermissionSerializer.DateRangeSerializer()
        dataPushUrl = serializers.CharField()
        keyMaterial = KeyMaterialSerializer()

    transactionId = serializers.UUIDField()
    hiRequest = HIRequestSerializer()
