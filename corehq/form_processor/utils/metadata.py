import logging
from copy import copy

from jsonobject.api import re_date

from dimagi.utils.parsing import json_format_datetime
from corehq.util.dates import iso_string_to_datetime


def scrub_meta(xform):
    """
    Cleans up old format metadata to our current standard.

    Does NOT save the doc, but returns whether the doc needs to be saved.
    """
    property_map = {'TimeStart': 'timeStart',
                    'TimeEnd': 'timeEnd',
                    'chw_id': 'userID',
                    'DeviceID': 'deviceID',
                    'uid': 'instanceID'}

    if not hasattr(xform, 'form'):
        return

    # hack to make sure uppercase meta still ends up in the right place
    found_old = False
    if 'Meta' in xform.form:
        xform.form['meta'] = xform.form['Meta']
        del xform.form['Meta']
        found_old = True
    if 'meta' in xform.form:
        meta_block = xform.form['meta']
        # scrub values from 0.9 to 1.0
        if isinstance(meta_block, list):
            if isinstance(meta_block[0], dict):
                # if it's a list of dictionaries, arbitrarily pick the first one
                # this is a pretty serious error, but it's also recoverable
                xform.form['meta'] = meta_block = meta_block[0]
                logging.error((
                    'form %s contains multiple meta blocks. '
                    'this is not correct but we picked one abitrarily'
                ) % xform.get_id)
            else:
                # if it's a list of something other than dictionaries.
                # don't bother scrubbing.
                logging.error('form %s contains a poorly structured meta block.'
                              'this might cause data display problems.')
        if isinstance(meta_block, dict):
            for key in meta_block:
                if key in property_map and property_map[key] not in meta_block:
                    meta_block[property_map[key]] = meta_block[key]
                    del meta_block[key]
                    found_old = True

    return found_old


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
