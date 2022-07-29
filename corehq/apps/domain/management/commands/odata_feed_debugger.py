import json
import os

from django.core.management.base import BaseCommand
from corehq.apps.app_manager.models import Application


class Command(BaseCommand):
    help = "Tool for debugging odata feed live on prod"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'app_id',
        )

    def handle(self, domain, app_id, **options):
        results = Application.get_db().view(
            'app_manager/saved_app',
            startkey=[domain, app_id, {}],
            endkey=[domain, app_id],
            descending=True,
            reduce=False,
            include_docs=True,
        ).all()
        for result in results:
            build_id = result['id']
            filename = f'{domain}-{build_id}.json'
            doc = result['doc']
            del doc['_id']
            del doc['_rev']
            filepath = os.path.join('/home/cchq/mcn-test/', filename)
            with open(filepath, 'w') as jsonfile:
                jsonfile.write(json.dumps(doc))
            command = f"AWS_PROFILE=commcare-production:session scp -o " \
                      f"StrictHostKeyChecking=no -o 'ProxyCommand=aws ssm " \
                      f"start-session --target %h --document-name AWS-StartSSHSession " \
                      f"--parameters portNumber=%p' " \
                      f"biyeun@i-03b1636303cb209d4:{filepath} " \
                      f"/Users/biyeun/Documents/Dimagi/mcn/{filename}"
            self.stdout.write(f'{command}\n\n')
