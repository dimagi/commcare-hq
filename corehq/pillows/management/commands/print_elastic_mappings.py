import argparse
import sys
from textwrap import dedent

from django.core.management.base import BaseCommand

from corehq.apps.es.client import manager
from corehq.apps.es.transient_util import doc_adapter_from_cname
from corehq.apps.es.utils import mapping_sort_key
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.apps.es.mappings.const import NULL_VALUE

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
        parser.add_argument("-t", "--transforms", metavar="TRANSFORMS", default="",
            help=f"perform transforms on the mapping, chain multiple by "
                 f"providing a comma-delimited list (options: "
                 f"{', '.join(sorted(ALL_TRANSFORMS))}), default is no transforms")
        parser.add_argument("mapping_ident", metavar="ID", help=(
            "Print the mapping for %(metavar)s. To print the mapping from "
            "code, specify an index canonical name (e.g. 'cases', 'sms', etc). "
            "To print the mapping fetched from Elasticsearch, specify a "
            "colon-delimited index name and index '_type' (e.g. "
            "'hqcases_2016-03-04:case', 'smslogs_2020-01-28:sms', etc)."
        ))

    def handle(self, mapping_ident, **options):
        if options["no_names"]:
            namespace = {}
        else:
            namespace = MAPPING_SPECIAL_VALUES
        try:
            adapter = doc_adapter_from_cname(mapping_ident)
        except KeyError:
            index_name, x, type_ = mapping_ident.partition(":")
            mapping = manager.index_get_mapping(index_name, type_) or {}
        else:
            mapping = adapter.mapping
        for key in (k.strip() for k in options["transforms"].split(",")):
            if key:
                self.stderr.write(f"applying transform: {key}\n", style_func=lambda x: x)
                mapping = ALL_TRANSFORMS[key](mapping)
        print_formatted(
            mapping,
            namespace,
            dict_sort_key=mapping_sort_key,
            stream=options["outfile"],
        )


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
    elif isinstance(mapping, (tuple, list, set)):
        return [transform_multi_field(v) for v in mapping]
    else:
        return mapping


def transform_string_to_text_and_keyword(mapping, key=None):
    """
    ``string`` fields have been replaced by ``text`` and ``keyword`` fields.
    The string keyword should be replaced in following manner.

        string + not_analyzed => keyword
        string => text

    See - https://www.elastic.co/guide/en/elasticsearch/reference/5.0/breaking_50_mapping_changes.html#breaking_50_mapping_changes  # noqa E501

    Tranforms-
    a)  "name": {
            "index": "not_analyzed",
            "type": "string"
        }
        To:
        "name": {
            "type": "keyword"
        }


    b)   "address": {
            "type": "string"
        }
        To:
        "address": {
            "type": "text"
        }
    """
    if isinstance(mapping, dict):
        if mapping.get("type") == "string":
            mapping = mapping.copy()
            if key is None:
                raise ValueError(f"'string' property {key!r} is missing "
                                 f"the 'default' field: {mapping}")
            if mapping.get("index") == "not_analyzed":
                mapping["type"] = "keyword"
            else:
                mapping["type"] = "text"
            if mapping.get("index"):
                del mapping["index"]
        return {k: transform_string_to_text_and_keyword(v, k) for k, v in mapping.items()}
    elif isinstance(mapping, (tuple, list, set)):
        return [transform_string_to_text_and_keyword(v) for v in mapping]
    else:
        return mapping


ALL_TRANSFORMS = {
    "multi_field": transform_multi_field,
    "string": transform_string_to_text_and_keyword
}
