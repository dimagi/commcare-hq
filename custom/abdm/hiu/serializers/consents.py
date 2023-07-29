from rest_framework import serializers

from custom.abdm.const import (
    CONSENT_PURPOSES,
    CONSENT_PURPOSES_REF_URI,
    GATEWAY_CONSENT_STATUS_CHOICES,
    HI_TYPES,
)
from custom.abdm.hiu.models import HIUConsentArtefact, HIUConsentRequest
from custom.abdm.hiu.serializers.base import (
    GatewayCareContextSerializer,
    GatewayErrorSerializer,
    GatewayIdSerializer,
    GatewayNotificationSerializer,
    GatewayPermissionSerializer,
    GatewayPurposeSerializer,
    GatewayRequestBaseSerializer,
    GatewayRequesterSerializer,
    GatewayResponseReferenceSerializer,
)
from custom.abdm.utils import validate_for_future_date, validate_for_past_date


class HIUGenerateConsentSerializer(serializers.Serializer):
    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=CONSENT_PURPOSES)
        refUri = serializers.CharField(default=CONSENT_PURPOSES_REF_URI)
        text = serializers.SerializerMethodField(method_name='get_code_text')

        def get_code_text(self, obj):
            return next(x[1] for x in CONSENT_PURPOSES if x[0] == obj['code'])

    class PermissionSerializer(GatewayPermissionSerializer):
        class DateRangeSerializer(serializers.Serializer):
            vars()['from'] = serializers.DateTimeField(validators=[validate_for_past_date])
            to = serializers.DateTimeField(validators=[validate_for_past_date])

        dateRange = DateRangeSerializer()
        dataEraseAt = serializers.DateTimeField(validators=[validate_for_future_date])

    purpose = PurposeSerializer()
    patient = GatewayIdSerializer()
    hip = GatewayIdSerializer(required=False)
    hiu = GatewayIdSerializer()
    careContexts = serializers.ListField(required=False, child=GatewayCareContextSerializer(), min_length=1)
    requester = GatewayRequesterSerializer()
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HI_TYPES), min_length=1)
    permission = PermissionSerializer()


class HIUConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = HIUConsentRequest
        exclude = ('gateway_request_id', )


class HIUConsentArtefactSerializer(serializers.ModelSerializer):
    class Meta:
        model = HIUConsentArtefact
        exclude = ('gateway_request_id', )


class GatewayConsentRequestOnInitSerializer(GatewayRequestBaseSerializer):
    consentRequest = GatewayIdSerializer(required=False)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()


class GatewayConsentRequestNotifySerializer(GatewayRequestBaseSerializer):
    notification = GatewayNotificationSerializer()


class GatewayConsentRequestOnFetchSerializer(GatewayRequestBaseSerializer):
    class ConsentSerializer(serializers.Serializer):

        class ConsentDetailSerializer(serializers.Serializer):
            schemaVersion = serializers.CharField(required=False)
            consentId = serializers.UUIDField()
            createdAt = serializers.DateTimeField()
            patient = GatewayIdSerializer()
            careContexts = serializers.ListField(child=GatewayCareContextSerializer(), min_length=1)
            purpose = GatewayPurposeSerializer()
            hip = GatewayIdSerializer()
            hiu = GatewayIdSerializer()
            consentManager = GatewayIdSerializer()
            requester = GatewayRequesterSerializer()
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HI_TYPES), min_length=1)
            permission = GatewayPermissionSerializer()

        status = serializers.ChoiceField(choices=GATEWAY_CONSENT_STATUS_CHOICES)
        consentDetail = ConsentDetailSerializer()
        signature = serializers.CharField()

    consent = ConsentSerializer(required=False)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()
