import logging

from django.core.management import CommandError
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.xform import XFormPillow
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import XFormInstance


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'hqadmin/forms_over_time'
    pillow_class = XFormPillow

    def handle(self, *args, **options):
        if not options.get('bulk', False):
            raise CommandError('{} must be called with --bulk'
                               .format(self.__module__))
        super(Command, self).handle(*args, **options)

    def custom_filter(self, view_row):
        if view_row and 'xmlns' in view_row:
            return view_row['xmlns'] != DEVICE_LOG_XMLNS
        else:
            logging.warning('Unexpected input to custom_filter: {}'.format(view_row))
            return False
