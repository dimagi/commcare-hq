from rest_framework import serializers

from custom.abdm.const import (
    CONSENT_PURPOSES,
    CONSENT_PURPOSES_REF_URI,
    HI_TYPES,
)
from custom.abdm.hiu.models import HIUConsentRequest
from custom.abdm.hiu.serializers.base import (
    GatewayCareContextSerializer,
    GatewayIdSerializer,
    GatewayPermissionSerializer,
    GatewayRequesterSerializer,
)
from custom.abdm.utils import past_date_validator, future_date_validator


class HIUGenerateConsentSerializer(serializers.Serializer):
    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=CONSENT_PURPOSES)
        refUri = serializers.CharField(default=CONSENT_PURPOSES_REF_URI)
        text = serializers.SerializerMethodField(method_name='get_code_text')

        def get_code_text(self, obj):
            return next(x[1] for x in CONSENT_PURPOSES if x[0] == obj['code'])

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
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HI_TYPES), min_length=1)
    permission = PermissionSerializer()


class HIUConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = HIUConsentRequest
        exclude = ('gateway_request_id', )
