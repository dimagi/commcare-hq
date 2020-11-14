import logging

from django.core.management.base import BaseCommand

from .corrupt_couch import setup_logging
from ...corrupt_couch import DOC_TYPES_BY_NAME
from ...corrupt_couch_nodes import (
    check_node_integrity,
    get_dbname,
    get_node_dbs,
    print_missing_ids
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Query stand-alone couch nodes for missing doc ids'

    def add_arguments(self, parser):
        parser.add_argument('nodes', help="comma-delimited list of node IP:PORT pairs")
        parser.add_argument('doc_name', choices=list(DOC_TYPES_BY_NAME))
        parser.add_argument('--range', dest="id_range", help="Doc id range XXXX..ZZZZ")
        parser.add_argument('--check-node-integrity', dest="check", action="store_true")
        parser.add_argument('--verbose', action="store_true")

    def handle(self, nodes, doc_name, id_range, **options):
        setup_logging(options["verbose"])
        id_range = id_range.split("..", 1) if id_range else ("", "")
        dbname = get_dbname(doc_name)
        dbs = get_node_dbs(nodes.split(","), dbname)
        run = check_node_integrity if options["check"] else print_missing_ids
        try:
            run(dbs, id_range)
        except KeyboardInterrupt:
            log.info("abort.")
