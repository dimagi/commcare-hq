import logging
from dateutil.parser import parse as parse_date

from django.core.management.base import BaseCommand

from ...corrupt_couch import count_missing_ids, DOC_TYPES_BY_NAME

START = parse_date('2020-10-16')
END = parse_date('2020-10-18')


class Command(BaseCommand):
    help = 'Check for or fix corrupt couch db'

    def add_arguments(self, parser):
        parser.add_argument('command', choices=["count-missing", "fix-missing"])
        parser.add_argument('domain')
        parser.add_argument('doc_name', choices=list(DOC_TYPES_BY_NAME) + ["ALL"])
        parser.add_argument('--date-range', help="YYYY-MM-DD..YYYY-MM-DD or 'ALL'")
        parser.add_argument('--verbose', action="store_true")

    def handle(self, command, domain, doc_name=None, date_range=None, **options):
        setup_logging(options["verbose"])
        if date_range is None:
            date_range = (START, END)
        else:
            start, end = date_range.split("..")
            date_range = parse_date(start), parse_date(end)
        if command == "count-missing":
            count_missing_ids(domain, doc_name, date_range)
        else:
            raise NotImplementedError


def setup_logging(debug=False):
    logging.root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in logging.root.handlers:
        if handler.name in ["file", "console"]:
            handler.setLevel(logging.DEBUG)
