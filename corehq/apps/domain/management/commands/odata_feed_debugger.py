import json

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
            doc_string = json.dumps(result['doc'])
            if 'formid' in doc_string:
                print('found formid')
                print(build_id)
