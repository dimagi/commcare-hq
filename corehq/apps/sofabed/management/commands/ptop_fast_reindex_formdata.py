from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.sofabed import FormDataPillow
from couchforms.models import XFormInstance

DEVICEREPORT = 'http://code.javarosa.org/devicereport'

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of SQL form data index"

    doc_class = XFormInstance
    view_name = 'couchforms/by_xmlns'
    pillow_class = FormDataPillow
    own_index_exists = False

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        if 'doc' in view_row:
            view_row = view_row['doc']

        if 'xmlns' in view_row:
            return view_row['xmlns'] != DEVICEREPORT
        elif 'key' in view_row:
            return view_row['key'] != DEVICEREPORT
        elif 'doc' in view_row and 'xmlns' in view_row['doc']:
            return view_row['doc']['xmlns'] != DEVICEREPORT
        else:
            return True

