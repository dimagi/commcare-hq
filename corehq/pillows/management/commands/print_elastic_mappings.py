import argparse
import sys
from textwrap import dedent

from django.core.management.base import BaseCommand

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings import CANONICAL_NAME_INFO_MAP
from corehq.pillows.mappings.const import NULL_VALUE
from corehq.pillows.mappings.utils import fetch_elastic_mapping

from .utils import print_formatted

MAPPING_SPECIAL_VALUES = {
    "DATE_FORMATS_ARR": DATE_FORMATS_ARR,
    "DATE_FORMATS_STRING": DATE_FORMATS_STRING,
    "NULL_VALUE": NULL_VALUE,
}


class Command(BaseCommand):

    help = dedent("""\
        Print Elasticsearch index mappings.

        Designed for:

        1. Printing mappings in a standard, consistent format.
        2. Using the verbatim output to update mapping source code.
    """)

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        # adding `formatter_class` to kwargs causes BaseCommand to specify it twice
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument("-o", "--outfile", metavar="FILE",
            type=argparse.FileType("w"), default=sys.stdout,
            help="write output to %(metavar)s rather than STDOUT")
        parser.add_argument("--no-names", action="store_true", default=False,
            help="do not replace special values with names")
        parser.add_argument("--from-elastic", action="store_true", default=False,
            help="pull mappings from elastic index instead of code definitions")
        parser.add_argument("cname", metavar="INDEX", choices=sorted(CANONICAL_NAME_INFO_MAP),
            help="print mapping for %(metavar)s")

    def handle(self, cname, **options):
        if options["no_names"]:
            namespace = {}
        else:
            namespace = MAPPING_SPECIAL_VALUES
        index_info = CANONICAL_NAME_INFO_MAP[cname]
        if options["from_elastic"]:
            mapping = fetch_elastic_mapping(index_info.alias, index_info.type)
        else:
            mapping = index_info.mapping
        print_formatted(mapping, namespace, stream=options["outfile"])
