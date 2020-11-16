import logging

import attr
from django.core.management.base import BaseCommand, CommandError

from ...corrupt_couch import count_missing_ids, repair_missing_ids, DOC_TYPES_BY_NAME


class Command(BaseCommand):
    help = 'Check for or fix corrupt couch db'

    def add_arguments(self, parser):
        parser.add_argument('command', choices=["count-missing", "repair"])
        parser.add_argument('doc_name', choices=list(DOC_TYPES_BY_NAME) + ["ALL"])
        parser.add_argument('--domain')
        parser.add_argument('--doc-type')
        parser.add_argument('--range', dest="view_range", help="""
            View key range. May be dates YYYY-MM-DD..YYYY-MM-DD or IDs
            XXXX..ZZZZ, depending on the view being queried.
        """)
        parser.add_argument('--missing', help="""
            Path to file containing a list of newline-delimited missing ids.
            Only valid with `repair` and not valid with --domain, --doc-type,
            or --range. Unrepairable missing ids are printed to stdout.
        """)
        parser.add_argument('--min-tries', type=int, default=10, help="default: 10")
        parser.add_argument('--verbose', action="store_true")

    def handle(self, command, doc_name, domain, doc_type, view_range, missing, min_tries, **options):
        if missing:
            if command != "repair":
                raise CommandError(f"cannot {command} with --missing")
            if doc_name == "ALL":
                raise CommandError("cannot repair 'ALL' with --missing")
            if domain or doc_type or view_range:
                raise CommandError("--missing cannot be used with --domain, "
                                   "--doc-type, or --range")
        setup_logging(options["verbose"])
        if view_range is not None:
            view_range = view_range.split("..", 1)
        params = QueryParams(domain, doc_name, doc_type, view_range)
        repair = command == "repair"
        if repair and missing:
            repair_missing_ids(doc_name, missing, min_tries)
        else:
            count_missing_ids(min_tries, params, repair=repair)


def setup_logging(debug=False):
    logging.root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in logging.root.handlers:
        if handler.name in ["file", "console"]:
            handler.setLevel(logging.DEBUG)


@attr.s
class QueryParams:
    domain = attr.ib()
    doc_name = attr.ib()
    doc_type = attr.ib()
    view_range = attr.ib()
