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

    sort_key_include_docs = True

    def full_couch_view_iter(self):
        # copied from couchforms/_design/filters/xforms.js
        doc_types = [
            'XFormInstance',
            'XFormArchived',
            'XFormError',
            'XFormDeprecated',
            'XFormDuplicate',
            'XFormInstance-Deleted',
            'HQSubmission',
            'SubmissionErrorLog',
        ]

        for doc_type in doc_types:
            rows = self.paginate_view(
                self.db,
                self.view_name,
                reduce=False,
                include_docs=True,
                startkey=[doc_type],
                endkey=[doc_type, {}],
            )
            for row in rows:
                yield row

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

    @staticmethod
    def sort_key(row):
        return row['doc'].get('received_on') or 'None'
