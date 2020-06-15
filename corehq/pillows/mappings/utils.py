import json
import os
import copy

from django.conf import settings
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING


def mapping_from_json(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        data = (f.read()
                .replace('"__DATE_FORMATS_STRING__"', json.dumps(DATE_FORMATS_STRING))
                .replace('"__DATE_FORMATS_ARR__"', json.dumps(DATE_FORMATS_ARR)))
        mapping = json.loads(data)
    return mapping


def transform_for_es7(original_mapping):
    mapping = copy.deepcopy(original_mapping)
    mapping = _transform_types(mapping)
    if "_all" in mapping:
        mapping.pop("_all")
    return mapping


def _transform_types(mapping):
    """
    Replaces mapping types to be compatible with Elasticsearch version 7

    String fileds are text/keyword depending on analyzed or not
        {"type": "string", "index", "analyzed", **kw} --> {"type": "text", **kw}
        {"type": "string", "index", "not_analyzed", **kw} --> {"type": "keyword", **kw}
        {"type": "string", **kw} --> {"type": "text", **kw}

    multi_field is dropped since 'fields' attrib captures the type
        {"type": "multi_field", **kw} --> {"type": "text", **kw}

    '_all' and 'include_in_all' are dropped

    """
    if settings.ELASTICSEARCH_MAJOR_VERSION != 7:
        # v1 and v2 have same mapping
        return mapping

    if isinstance(mapping, dict):
        items = mapping.items()
        if ("type", "string") in items:
            if ("index", "analyzed") in items:
                mapping["type"] = "text"
                mapping.pop("index")
            elif ("index", "not_analyzed") in items:
                mapping["type"] = "keyword"
                mapping.pop("index")
            else:
                mapping["type"] = "text"
            if "null_value" in mapping:
                # null_value is not supported for text types
                mapping.pop("null_value")
        elif ("type", "multi_field") in items:
            # multi_field is replaced by just fields
            mapping["type"] = "text"
        unsupported_attribs = [
            "include_in_all", "_all",
            'geohash', 'geohash_prefix', 'geohash_precision', 'lat_lon'
        ]
        for attr in unsupported_attribs:
            if attr in mapping:
                mapping.pop(attr)
        return {k: _transform_types(v) for k, v in mapping.items()}
    elif isinstance(mapping, list):
        return [_transform_types(i) for i in mapping]
    else:
        return mapping
