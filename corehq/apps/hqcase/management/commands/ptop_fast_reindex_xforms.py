from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.xform import XFormPillow
from couchforms.models import XFormInstance

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = XFormInstance
    view_name = 'hqadmin/forms_over_time'
    pillow_class = XFormPillow

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

