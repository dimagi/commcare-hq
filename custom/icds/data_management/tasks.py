from celery.task import task

from custom.icds.data_management.models import DataManagementRequest


@task(queue='background_queue')
def execute_data_management(request_id):
    processed, skipped = DataManagementRequest.objects.get(pk=request_id).execute()
