from rest_framework import serializers


CONSENT_PURPOSES = [('CAREMGT', ''), ('BTG', ''), ('PUBHLTH', ''), ('HPAYMT', ''), ('DSRCH', ''), ('PATRQT', '')]
HI_TYPES = [('OPConsultation', ''), ('Prescription', ''), ('DischargeSummary', ''), ('DiagnosticReport', ''),
            ('ImmunizationRecord', ''), ('HealthDocumentRecord', ''), ('WellnessRecord', '')]
DATA_ACCESS_MODES = [(c, c) for c in ['VIEW', 'STORE', 'QUERY', 'STREAM']]
TIME_UNITS = [(c, c) for c in ['HOUR', 'WEEK', 'DAY', 'MONTH', 'YEAR']]


class RequestBaseSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class ResponseSerializer(serializers.Serializer):
    requestId = serializers.UUIDField()


class ConsentInitSerializer(serializers.Serializer):

    class PurposeSerializer(serializers.Serializer):
        code = serializers.ChoiceField(choices=CONSENT_PURPOSES)
        refUri = 'http://terminology.hl7.org/ValueSet/v3-PurposeOfUse'
        # TODO Add text dynamically

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
    patient = IdSerializer()
    hip = IdSerializer()
    careContexts = serializers.ListField(required=False, child=CareContextSerializer(), min_length=1)
    hiu = IdSerializer()
    requester = RequesterSerializer()
    hiTypes = serializers.ListField(child=serializers.ChoiceField(choices=HI_TYPES), min_length=1)
    permission = PermissionSerializer()
