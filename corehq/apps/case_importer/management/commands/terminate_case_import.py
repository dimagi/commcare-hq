from django.core.management import BaseCommand

from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from soil.progress import STATES


class Command(BaseCommand):
    help = "Manually terminate an ongoing case import. Makes no attempt to roll back any applied changes."

    def add_arguments(self, parser):
        parser.add_argument('upload_id')

    def handle(self, upload_id, **options):
        record = CaseUploadRecord.objects.get(upload_id=upload_id)
        record.task.revoke(terminate=True)
        record.task_status_json.state = STATES.failed
        record.save()
