from contextlib import contextmanager

from django.core.management.base import BaseCommand

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings.const import NULL_VALUE
from corehq.pillows.mappings import CANONICAL_NAME_INFO_MAP

from .utils import pprint

MAPPING_SPECIAL_VALUES = {
    "DATE_FORMATS_ARR": DATE_FORMATS_ARR,
    "DATE_FORMATS_STRING": DATE_FORMATS_STRING,
    "NULL_VALUE": NULL_VALUE,
}


class Command(BaseCommand):

    help = "Print Elasticsearch index mappings."

    def add_arguments(self, parser):
        parser.add_argument("-o", "--outfile", metavar="FILE",
            help="write output to %(metavar)s rather than STDOUT")
        parser.add_argument("--no-names", action="store_true", default=False,
            help="do not replace special values with names")
        parser.add_argument("cname", metavar="INDEX", choices=sorted(CANONICAL_NAME_INFO_MAP),
            help="print mapping for %(metavar)s")

    def handle(self, cname, **options):
        outpath = options["outfile"]
        if options["no_names"]:
            namespace = {}
        else:
            namespace = MAPPING_SPECIAL_VALUES
        if outpath is None:
            outpath = self.stdout._out  # Why, OutputWrapper.write()? Why?

            @contextmanager
            def opener(file, mode):
                yield file

        else:
            opener = open
        with opener(outpath, "w") as outfile:
            mapping = CANONICAL_NAME_INFO_MAP[cname].mapping
            pprint(mapping, namespace, stream=outfile)
