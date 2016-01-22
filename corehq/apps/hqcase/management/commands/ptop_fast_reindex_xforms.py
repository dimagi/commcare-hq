import logging

from django.core.management import CommandError
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.xform import XFormPillow
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import XFormInstance


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    pillow_class = XFormPillow

    view_name = 'all_docs/by_doc_type'

    def get_extra_view_kwargs(self):
        return {
            'startkey': ['XFormInstance'],
            'endkey': ['XFormInstance', {}],
        }

    def handle(self, *args, **options):
        if not options.get('bulk', False):
            raise CommandError('{} must be called with --bulk'
                               .format(self.__module__))
        super(Command, self).handle(*args, **options)

    def custom_filter(self, view_row):
        if 'xmlns' in view_row:
            return view_row['xmlns'] != DEVICE_LOG_XMLNS
        else:
            logging.warning('Unexpected input to custom_filter: {}'.format(view_row))
            return False
