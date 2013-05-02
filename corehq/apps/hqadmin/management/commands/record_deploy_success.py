from django.core.management.base import BaseCommand
from corehq.apps.hqadmin.models import HqDeploy
from datetime import datetime
from optparse import make_option

class Command(BaseCommand):
    help = "Creates an HqDeploy document to record a successful deployment."
    args = "[user]"

    option_list = BaseCommand.option_list + (
        make_option('--user', help='User', default=False),
    )
    
    def handle(self, *args, **options):
        deploy = HqDeploy(
            date=datetime.utcnow(),
            user=options['user']
        )
        deploy.save()
        