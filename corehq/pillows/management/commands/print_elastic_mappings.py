import argparse
import sys
from textwrap import dedent

from django.core.management.base import BaseCommand

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings import CANONICAL_NAME_INFO_MAP
from corehq.pillows.mappings.const import NULL_VALUE
from corehq.pillows.mappings.tests.utils import fetch_elastic_mapping

from .utils import pprint

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
        3. Generating transformed mappings (e.g. for upgrading mappings to
           modern formats) with an iterative workflow where the transform logic
           is represented as tested, reviewable code.
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
        parser.add_argument("-t", "--transforms", metavar="TRANSFORMS", default="",
            help=f"perform transforms on the mapping, chain multiple by "
                 f"providing a comma-delimited list (options: "
                 f"{', '.join(sorted(ALL_TRANSFORMS))}), default is no transforms")
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
        for key in iter(k.strip() for k in options["transforms"].split(",")):
            if key:
                self.stderr.write(f"applying transform: {key}\n", style_func=lambda x: x)
                mapping = ALL_TRANSFORMS[key](mapping)
        pprint(mapping, namespace, stream=options["outfile"])


def transform_multi_field(mapping, key=None):
    """Recursively convert 'multi_field' type (deprecated since version 0.9) to
    'string' in an Elastic mapping. The field named the same as the property is
    no longer necessary since the top-level property becomes the default in
    versions >=1.0.
    See: https://www.elastic.co/guide/en/elasticsearch/reference/1.7/_multi_fields.html

    Transforms:
        "city": {
            "fields": {
                "city":  {"type": "string", "index": "analyzed"},
                "exact": {"type": "string", "index": "not_analyzed"},
            },
            "type": "multi_field"
        }
    To:
        "city": {
            "fields": {
                "exact": {"type": "string", "index": "not_analyzed"}
            },
            "type": "string"
        }
    """
    if isinstance(mapping, dict):
        if "fields" in mapping and mapping.get("type") == "multi_field":
            mapping = mapping.copy()
            if key is None or key not in mapping["fields"]:
                raise ValueError(f"'multi_field' property {key!r} is missing "
                                 f"the 'default' field: {mapping}")
            mapping.update(mapping["fields"].pop(key))
            if mapping.get("index") == "analyzed":
                # {"index": "analyzed"} is the default
                del mapping["index"]
        return {k: transform_multi_field(v, k) for k, v in mapping.items()}
    if isinstance(mapping, (tuple, list, set)):
        return [transform_multi_field(v) for v in mapping]
    return mapping


ALL_TRANSFORMS = {
    "multi_field": transform_multi_field,
}
