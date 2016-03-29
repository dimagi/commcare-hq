import json
import os
import string

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.util.elastic import es_index


CASE_SEARCH_INDEX = es_index("case_search_2016-03-15")


def _CASE_SEARCH_MAPPING():
    with open(os.path.join(os.path.dirname(__file__), 'case_search_mapping.json')) as f:
        template = string.Template(f.read())
        data = template.substitute(
            DATE_FORMATS_STRING=json.dumps(DATE_FORMATS_STRING),
            DATE_FORMATS_ARR=json.dumps(DATE_FORMATS_ARR))
        mapping = json.loads(data)
    return mapping

CASE_SEARCH_MAPPING = _CASE_SEARCH_MAPPING()
