from rest_framework import serializers

from corehq.const import USER_DATETIME_FORMAT
from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS
from custom.icds.data_management.models import DataManagementRequest


class DataManagementRequestSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = DataManagementRequest
        fields = ['db_alias', 'start_date', 'end_date', 'domain',
                  'initiated_by', 'error', 'status']

    def to_representation(self, instance):
        ret = super(DataManagementRequestSerializer, self).to_representation(instance)
        task = DATA_MANAGEMENT_TASKS.get(instance.slug)
        ret['name'] = task.name if task else instance.slug
        ret['created_at'] = instance.created_at.strftime(USER_DATETIME_FORMAT)
        ret['started_on'] = instance.started_on.strftime(USER_DATETIME_FORMAT) if instance.started_on else ''
        ret['ended_on'] = instance.ended_on.strftime(USER_DATETIME_FORMAT) if instance.ended_on else ''
        ret['status_text'] = dict(DataManagementRequest.STATUS_CHOICES).get(instance.status)
        return ret
