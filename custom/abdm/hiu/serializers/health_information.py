from rest_framework import serializers

from custom.abdm.serializers import KeyMaterialSerializer, GatewayRequestBaseSerializer, GatewayIdSerializer, \
    GatewayErrorSerializer, GatewayResponseReferenceSerializer
from custom.abdm.const import HEALTH_INFORMATION_MEDIA_TYPE


class HIURequestHealthInformationSerializer(serializers.Serializer):
    artefact_id = serializers.UUIDField()


class HIUReceiveHealthInformationSerializer(serializers.Serializer):
    pageNumber = serializers.IntegerField()
    pageCount = serializers.IntegerField()
    transactionId = serializers.UUIDField()
    entries = serializers.ListField(min_length=1)
    keyMaterial = KeyMaterialSerializer()

    def validate_entries(self, value):
        for entry in value:
            if entry.get('content'):
                EntryContentSerializer(data=entry).is_valid(raise_exception=True)
            elif entry.get('link'):
                EntryLinkSerializer(data=entry).is_valid(raise_exception=True)
            else:
                raise serializers.ValidationError("Entry should contain either 'content' or link'")
        return value


class EntrySerializer(serializers.Serializer):
    media = serializers.ChoiceField(choices=[HEALTH_INFORMATION_MEDIA_TYPE])
    checksum = serializers.CharField()
    careContextReference = serializers.CharField()


class EntryContentSerializer(EntrySerializer):
    content = serializers.CharField()


class EntryLinkSerializer(EntrySerializer):
    link = serializers.CharField()


class GatewayHiRequestSerializer(serializers.Serializer):
    transactionId = serializers.UUIDField()
    sessionStatus = serializers.ChoiceField(choices=['REQUESTED', 'ACKNOWLEDGED'])


class GatewayHealthInformationOnRequestSerializer(GatewayRequestBaseSerializer):
    hiRequest = GatewayHiRequestSerializer(required=False)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()
