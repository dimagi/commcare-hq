from rest_framework import serializers

from custom.icds.data_management.const import DATA_MANAGEMENT_TASKS
from custom.icds.data_management.models import DataManagementRequest


class DataManagementRequestSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = DataManagementRequest
        fields = ['db_alias', 'start_date', 'end_date']

    def to_representation(self, instance):
        ret = super(DataManagementRequestSerializer, self).to_representation(instance)
        task = DATA_MANAGEMENT_TASKS.get(instance.slug)
        ret['name'] = task.name if task else instance.slug
        ret['status'] = dict(DataManagementRequest.STATUS_CHOICES).get(instance.status)
        return ret
