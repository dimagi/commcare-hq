from fluff.management.commands.ptop_fast_reindex_fluff import FluffPtopReindexer
from couchforms.models import XFormInstance
from custom.opm.opm_reports.models import OpmCasePillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(FluffPtopReindexer):
    domain = 'opm'
    pillow_class = OpmCasePillow