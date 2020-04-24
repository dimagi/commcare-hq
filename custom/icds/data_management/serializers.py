from rest_framework import serializers

from corehq.const import USER_DATETIME_FORMAT
from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS
from custom.icds.data_management.models import DataManagementRequest


class DataManagementRequestSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format=USER_DATETIME_FORMAT)
    started_on = serializers.DateTimeField(format=USER_DATETIME_FORMAT)
    ended_on = serializers.DateTimeField(format=USER_DATETIME_FORMAT)

    class Meta(object):
        model = DataManagementRequest
        fields = ['db_alias', 'start_date', 'end_date', 'domain', 'created_at', 'started_on', 'ended_on',
                  'initiated_by', 'error', 'status']

    def to_representation(self, instance):
        ret = super(DataManagementRequestSerializer, self).to_representation(instance)
        task = DATA_MANAGEMENT_TASKS.get(instance.slug)
        ret['name'] = task.name if task else instance.slug
        ret['status_text'] = dict(DataManagementRequest.STATUS_CHOICES).get(instance.status)
        return ret
