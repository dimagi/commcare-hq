from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.fullxform import FullXFormPillow
from couchforms.models import XFormInstance

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'couchforms/by_xmlns'
    pillow_class = FullXFormPillow

    def custom_filter(self, view_row):
        """
        Custom filter if you want to do additional filtering based on the view

        Return true if to index, false if to SKIP
        """
        return view_row['key'] != 'http://code.javarosa.org/devicereport'
