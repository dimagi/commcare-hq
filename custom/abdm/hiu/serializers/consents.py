from rest_framework import serializers

from custom.abdm.const import (
    ConsentPurpose,
    HealthInformationType, STATUS_GRANTED, STATUS_DENIED, STATUS_REVOKED, STATUS_EXPIRED,
)
from custom.abdm.hiu.models import HIUConsentArtefact, HIUConsentRequest
from custom.abdm.serializers import (
    GatewayCareContextSerializer,
    GatewayErrorSerializer,
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayPurposeSerializer,
    GatewayRequestBaseSerializer,
    GatewayRequesterSerializer,
    GatewayResponseReferenceSerializer,
)
from custom.abdm.utils import future_date_validator, past_date_validator


class HIUGenerateConsentSerializer(serializers.Serializer):
    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=ConsentPurpose.CHOICES)
        refUri = serializers.CharField(default=ConsentPurpose.REFERENCE_URI)
        text = serializers.SerializerMethodField(method_name='get_code_text')

        def get_code_text(self, obj):
            return next(x[1] for x in ConsentPurpose.CHOICES if x[0] == obj['code'])

    class PermissionSerializer(GatewayPermissionSerializer):
        class DateRangeSerializer(serializers.Serializer):
            vars()['from'] = serializers.DateTimeField(validators=[past_date_validator])
            to = serializers.DateTimeField(validators=[past_date_validator])

        dateRange = DateRangeSerializer()
        dataEraseAt = serializers.DateTimeField(validators=[future_date_validator])

    purpose = PurposeSerializer()
    patient = GatewayIdSerializer()
    hip = GatewayIdSerializer(required=False)
    hiu = GatewayIdSerializer()
    careContexts = serializers.ListField(required=False, child=GatewayCareContextSerializer(), min_length=1)
    requester = GatewayRequesterSerializer()
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES),
                                    min_length=1)
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
            hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HealthInformationType.CHOICES),
                                            min_length=1)
            permission = GatewayPermissionSerializer()

        status = serializers.ChoiceField(choices=GATEWAY_CONSENT_STATUS_CHOICES)
        consentDetail = ConsentDetailSerializer(required=False, allow_null=True)
        signature = serializers.CharField(allow_null=True, allow_blank=True)


    consent = ConsentSerializer(required=False)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()


class GatewayNotificationSerializer(serializers.Serializer):
    consentRequestId = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=GATEWAY_CONSENT_STATUS_CHOICES)
    consentArtefacts = serializers.ListField(required=False, child=GatewayIdSerializer())


GATEWAY_CONSENT_STATUS_CHOICES = [(c, c) for c in [STATUS_GRANTED, STATUS_DENIED, STATUS_REVOKED,
                                                   STATUS_EXPIRED]]
