import io

from django.template.loader import render_to_string

from celery.task import task

from corehq.util.log import send_HTML_email
from custom.icds.data_management.models import DataManagementRequest
from custom.icds.data_management.serializers import (
    DataManagementRequestSerializer,
)


@task(queue='background_queue')
def execute_data_management(request_id):
    request = DataManagementRequest.objects.get(pk=request_id)
    processed, skipped, logs = request.execute()
    serialized = DataManagementRequestSerializer().to_representation(request)
    file_attachments = []
    for filename, filepath in logs.items():
        with open(filepath) as logfile:
            file_attachments.append({
                'title': filename,
                'file_obj': io.StringIO(logfile.read()),
                'mimetype': 'text/html',
            })
    subject = f"Data Management Task Result {serialized['name']} on {request.domain}"

    context = {
        'processed': processed,
        'skipped': skipped,
    }
    context.update(serialized)
    send_HTML_email(subject, request.initiated_by,
                    render_to_string('data_management/email/data_management.html', context),
                    file_attachments=file_attachments)
