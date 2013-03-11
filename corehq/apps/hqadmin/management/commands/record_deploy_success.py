from django.core.management.base import LabelCommand
from corehq.apps.hqadmin.models import HqDeploy
from datetime import datetime

class Command(LabelCommand):
    help = "Creates an HqDeploy document to record a successful deployment."
    args = ""
    label = ""
    
    def handle(self, *args, **options):
        deploy = HqDeploy(date=datetime.utcnow())
        deploy.save()
        