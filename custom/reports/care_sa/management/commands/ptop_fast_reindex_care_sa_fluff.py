from custom.reports.care_sa.models import CareSAFluffPillow
from fluff.management.commands.ptop_fast_reindex_fluff import FluffPtopReindexer

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(FluffPtopReindexer):
    domain = 'care-ihapc-live'
    pillow_class = CareSAFluffPillow
