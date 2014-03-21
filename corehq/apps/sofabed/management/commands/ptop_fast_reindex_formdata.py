from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.formdata import FormDataPillow
from couchforms.models import XFormInstance

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of SQL form data index"

    doc_class = XFormInstance
    view_name = 'hqadmin/forms_over_time'
    pillow_class = FormDataPillow
    own_index_exists = False

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        if 'xmlns' in view_row:
            return view_row['xmlns'] != 'http://code.javarosa.org/devicereport'
        elif 'key' in view_row:
            return view_row['key'] != 'http://code.javarosa.org/devicereport'
        else:
            return True

