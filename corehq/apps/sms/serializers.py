from corehq.apps.sms.models import SMS
from rest_framework import serializers


class SMSSerializer(serializers.ModelSerializer):
    _id = serializers.CharField(source='couch_id')
    messaging_subevent_id = serializers.IntegerField()

    class Meta:
        model = SMS
        exclude = ('couch_id', 'messaging_subevent')
