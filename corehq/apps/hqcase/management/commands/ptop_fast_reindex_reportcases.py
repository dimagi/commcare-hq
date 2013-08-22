from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import PtopReindexer
from corehq.pillows.reportcase import ReportCasePillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(PtopReindexer):
    help = "Fast reindex of case elastic index by using the case view and reindexing cases"

    doc_class = CommCareCase
    view_name = 'case/by_owner'
    pillow_class = ReportCasePillow
