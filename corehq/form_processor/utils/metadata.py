import logging
from copy import copy

from jsonobject.api import re_date

from dimagi.utils.parsing import json_format_datetime
from corehq.util.dates import iso_string_to_datetime


def clean_metadata(_meta_block):
    meta_block = copy(dict(_meta_block))
    if not meta_block:
        return meta_block
    meta_block = _remove_unused_meta_attributes(meta_block)
    meta_block['appVersion'] = _get_text_attribute(meta_block.get('appVersion'))
    meta_block['location'] = _get_text_attribute(meta_block.get('location'))
    meta_block = _parse_meta_times(meta_block)

    # also clean dicts on the return value, since those are not allowed
    for key in meta_block:
        if isinstance(meta_block[key], dict):
            meta_block[key] = _flatten_dict(meta_block[key])

    return meta_block


def _flatten_dict(dictionary):
    return ", ".join("{}:{}".format(k, v) for k, v in dictionary.items())


def _remove_unused_meta_attributes(meta_block):
    for key in meta_block.keys():
        # remove attributes from the meta block
        if key.startswith('@'):
            del meta_block[key]
    return meta_block


def _parse_meta_times(meta_block):
    for key in ("timeStart", "timeEnd"):
        if key not in meta_block:
            continue
        if meta_block[key]:
            if re_date.match(meta_block[key]):
                # this kind of leniency is pretty bad and making it midnight in UTC
                # is totally arbitrary here for backwards compatibility
                meta_block[key] += 'T00:00:00.000000Z'
            try:
                # try to parse to ensure correctness
                parsed = iso_string_to_datetime(meta_block[key])
                # and set back in the right format in case it was a date, not a datetime
                meta_block[key] = json_format_datetime(parsed)
            except Exception:
                logging.exception('Could not parse meta_block')
                # we couldn't parse it
                del meta_block[key]
        else:
            # it was empty, also a failure
            del meta_block[key]

    return meta_block


def _get_text_attribute(node):
    if node is None:
        return None
    if isinstance(node, dict) and '#text' in node:
        value = node['#text']
    elif isinstance(node, dict) and all(a.startswith('@') for a in node):
        return None
    else:
        value = node

    if not isinstance(value, basestring):
        value = unicode(value)
    return value
