import json
import os

from corehq.util.elastic import es_index


CASE_SEARCH_INDEX = es_index("case_search_2016-03-15")


def CASE_SEARCH_MAPPING():
    with open(os.path.join(os.path.dirname(__file__), 'case_search_mapping.json')) as f:
        mapping = json.load(f)
    return mapping
