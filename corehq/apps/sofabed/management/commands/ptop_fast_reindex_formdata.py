from django.core.management import CommandError
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.sofabed import FormDataPillow
from couchforms.models import XFormInstance


class Command(PtopReindexer):
    help = "Fast reindex of SQL form data index"

    doc_class = XFormInstance
    view_name = 'hqadmin/forms_over_time'
    pillow_class = FormDataPillow
    own_index_exists = False

    def handle(self, *args, **options):
        if options.get('bulk', False):
            # --bulk doesn't work
            # because FormDataPillow doesn't override process_bulk
            raise CommandError('{} cannot be called with --bulk'
                               .format(self.__module__))
        super(Command, self).handle(*args, **options)
