from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.domain import DomainPillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of domain elastic index by using the domain view and reindexing domains"

    doc_class = Domain
    view_name = 'domain/domains'
    pillow_class = DomainPillow
