from custom.reports.mc.models import MalariaConsortiumFluffPillow
from fluff.management.commands.ptop_fast_reindex_fluff import FluffPtopReindexer

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(FluffPtopReindexer):
    domain = 'mc-inscale'
    pillow_class = MalariaConsortiumFluffPillow


