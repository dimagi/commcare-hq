from rest_framework import serializers

from corehq.apps.sms.models import SMS, SQLMobileBackend


class SMSSerializer(serializers.ModelSerializer):
    _id = serializers.CharField(source='couch_id')
    messaging_subevent_id = serializers.IntegerField()
    custom_metadata = serializers.DictField()

    class Meta(object):
        model = SMS
        exclude = ('couch_id', 'messaging_subevent')


class MobileBackendSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = SQLMobileBackend
        exclude = ('inbound_api_key', 'extra_fields')
