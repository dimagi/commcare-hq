from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import SMS
from rest_framework import serializers


class SMSSerializer(serializers.ModelSerializer):
    _id = serializers.CharField(source='couch_id')
    messaging_subevent_id = serializers.IntegerField()
    custom_metadata = serializers.DictField()

    class Meta(object):
        model = SMS
        exclude = ('couch_id', 'messaging_subevent')
