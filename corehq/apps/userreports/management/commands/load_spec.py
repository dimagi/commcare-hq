from __future__ import print_function
import json
from optparse import make_option
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from dimagi.utils.decorators.log_exception import log_exception


class Command(BaseCommand):
    help = "Load a user configurable report data source or report spec from a json file"
    args = '<filename>'
    label = ""
    option_list = (
        make_option('--rebuild',
                    action='store_true',
                    dest='rebuild',
                    default=False,
                    help='Also rebuild indicator tables (has no affect for reports).'),
    )

    @log_exception()
    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Usage is load_data_source %s' % self.args)

        filename = args[0]
        with open(filename) as f:
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
                rebuild_indicators(to_save._id)
                print('...done!')
