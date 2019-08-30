import json

from django.core.management.base import BaseCommand

from couchdbkit import ResourceNotFound

from dimagi.utils.decorators.log_exception import log_exception

from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.tasks import rebuild_indicators


class Command(BaseCommand):
    help = "Load a user configurable report data source or report spec from a json file"

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument(
            '--rebuild',
            action='store_true',
            dest='rebuild',
            default=False,
            help='Also rebuild indicator tables (has no affect for reports).',
        )
        parser.add_argument(
            '--initiated-by', required=True, action='store',
            dest='initiated', help='Who initiated the action'
        )

    @log_exception()
    def handle(self, filename, **options):
        with open(filename, encoding='utf-8') as f:
            body = json.loads(f.read())

            # intentionally fails hard if bad or missing doc_type
            cls = {
                'DataSourceConfiguration': DataSourceConfiguration,
                'ReportConfiguration': ReportConfiguration,
            }[body['doc_type']]

            if '_id' in body:
                try:
                    rev = cls.get_db().get_rev(body['_id'])
                    body['_rev'] = rev
                except ResourceNotFound:
                    pass
            to_save = cls.wrap(body)
            to_save.validate()
            to_save.save()

            print('updated {}: "{}"'.format(to_save.doc_type, to_save))
            if options['rebuild'] and isinstance(to_save, DataSourceConfiguration):
                print('rebuilding table...')
                rebuild_indicators(to_save._id, initiated_by=options['initiated'], source='load_spec')
                print('...done!')
