from rest_framework import serializers

from custom.abdm.const import (
    AuthenticationMode,
    AuthFetchModesPurpose,
    RequesterType,
)
from custom.abdm.serializers import (
    GatewayErrorSerializer,
    GatewayRequestBaseSerializer,
    GatewayResponseReferenceSerializer,
)
from custom.abdm.user_auth.const import GENDER_CHOICES, IDENTIFIER_TYPE_CHOICES


class AuthFetchModesSerializer(serializers.Serializer):

    class RequesterSerializer(serializers.Serializer):
        type = serializers.ChoiceField(choices=RequesterType.CHOICES)
        id = serializers.CharField()

    id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
    requester = RequesterSerializer()


class GatewayAuthOnFetchModesSerializer(GatewayRequestBaseSerializer):

    class AuthSerializer(serializers.Serializer):
        purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
        modes = serializers.ListField(child=serializers.ChoiceField(choices=AuthenticationMode.CHOICES))

    auth = AuthSerializer(required=False, allow_null=True)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()


class AuthRequesterSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=RequesterType.CHOICES)
    id = serializers.CharField()


class AuthInitSerializer(serializers.Serializer):

    id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
    requester = AuthRequesterSerializer()
    authMode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES, required=False)

    def validate_authMode(self, data):
        if data == AuthenticationMode.DIRECT:
            raise serializers.ValidationError(f"'{AuthenticationMode.DIRECT}' Auth mode is not supported!")


class GatewayAuthOnInitSerializer(GatewayRequestBaseSerializer):

    class AuthSerializer(serializers.Serializer):

        class MetaSerializer(serializers.Serializer):
            hint = serializers.CharField(allow_null=True)
            expiry = serializers.CharField()

        transactionId = serializers.CharField()
        mode = serializers.ChoiceField(choices=AuthenticationMode.CHOICES)
        meta = MetaSerializer(required=False)

    auth = AuthSerializer(required=False, allow_null=True)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()


class AuthConfirmSerializer(serializers.Serializer):

    class CredentialSerializer(serializers.Serializer):

        class DemographicSerializer(serializers.Serializer):

            class IdentifierSerializer(serializers.Serializer):
                type = serializers.ChoiceField(choices=['MOBILE'])
                value = serializers.CharField()

            name = serializers.CharField()
            gender = serializers.ChoiceField(choices=GENDER_CHOICES)
            dateOfBirth = serializers.CharField()
            identifier = IdentifierSerializer(required=False)

        authCode = serializers.CharField(required=False)
        demographic = DemographicSerializer(required=False)

    transactionId = serializers.CharField()
    credential = CredentialSerializer()


class GatewayAuthOnConfirmSerializer(GatewayRequestBaseSerializer):

    class AuthSerializer(serializers.Serializer):

        class TokenValiditySerializer(serializers.Serializer):
            purpose = serializers.ChoiceField(choices=AuthFetchModesPurpose.CHOICES)
            requester = AuthRequesterSerializer()
            expiry = serializers.DateTimeField()
            limit = serializers.IntegerField()

        class PatientDemographicSerializer(serializers.Serializer):

            class IdentifierSerializer(serializers.Serializer):
                type = serializers.ChoiceField(choices=IDENTIFIER_TYPE_CHOICES)
                value = serializers.CharField()

            class AddressSerializer(serializers.Serializer):
                line = serializers.CharField(required=False)
                district = serializers.CharField(required=False)
                state = serializers.CharField(required=False)
                pincode = serializers.CharField(required=False)

            id = serializers.CharField()
            name = serializers.CharField()
            gender = serializers.ChoiceField(choices=GENDER_CHOICES)
            yearOfBirth = serializers.IntegerField()
            address = AddressSerializer(required=False, allow_null=True)
            identifier = IdentifierSerializer(required=False, allow_null=True)

        accessToken = serializers.CharField(required=False, allow_null=True)
        validity = TokenValiditySerializer(required=False, allow_null=True)
        patient = PatientDemographicSerializer(required=False, allow_null=True)

    auth = AuthSerializer(required=False, allow_null=True)
    error = GatewayErrorSerializer(required=False, allow_null=True)
    resp = GatewayResponseReferenceSerializer()
