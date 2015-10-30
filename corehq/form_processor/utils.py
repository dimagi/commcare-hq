import functools
import iso8601
import types
import collections
import pytz
import xml2json

from django.conf import settings
from dimagi.ext.jsonobject import re_loose_datetime
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.tzmigration import phone_timezones_should_be_processed
from corehq.toggles import USE_SQL_BACKEND


class ToFromGeneric(object):
    def to_generic(self):
        raise NotImplementedError()

    @classmethod
    def from_generic(cls, obj_dict):
        raise NotImplementedError()


def to_generic(fn):
    """
    Helper decorator to convert from a DB type to a generic type by calling 'to_generic'
    on the db type. e.g. FormData to XFormInstance
    """
    def _wrap(obj):
        if hasattr(obj, 'to_generic'):
            return obj.to_generic()
        elif isinstance(obj, (list, tuple)):
            return [_wrap(ob) for ob in obj]
        elif isinstance(obj, (types.GeneratorType, collections.Iterable)):
            return (_wrap(ob) for ob in obj)
        else:
            return obj

    @functools.wraps(fn)
    def _inner(*args, **kwargs):
        obj = fn(*args, **kwargs)
        return _wrap(obj)

    return _inner


def should_use_sql_backend(domain):
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override
    return USE_SQL_BACKEND.enabled(domain)


def extract_meta_instance_id(form):
    """Takes form json (as returned by xml2json)"""
    if form.get('Meta'):
        # bhoma, 0.9 commcare
        meta = form['Meta']
    elif form.get('meta'):
        # commcare 1.0
        meta = form['meta']
    else:
        return None

    if meta.get('uid'):
        # bhoma
        return meta['uid']
    elif meta.get('instanceID'):
        # commcare 0.9, commcare 1.0
        return meta['instanceID']
    else:
        return None


def convert_xform_to_json(xml_string):
    """
    takes xform payload as xml_string and returns the equivalent json
    i.e. the json that will show up as xform.form

    """

    try:
        name, json_form = xml2json.xml2json(xml_string)
    except xml2json.XMLSyntaxError as e:
        from couchforms import XMLSyntaxError
        raise XMLSyntaxError(u'Invalid XML: %s' % e)
    json_form['#type'] = name
    return json_form


def adjust_datetimes(data, parent=None, key=None):
    """
    find all datetime-like strings within data (deserialized json)
    and format them uniformly, in place.

    """
    # this strips the timezone like we've always done
    # todo: in the future this will convert to UTC
    if isinstance(data, basestring) and re_loose_datetime.match(data):
        try:
            matching_datetime = iso8601.parse_date(data)
        except iso8601.ParseError:
            pass
        else:
            if phone_timezones_should_be_processed():
                parent[key] = unicode(json_format_datetime(
                    matching_datetime.astimezone(pytz.utc).replace(tzinfo=None)
                ))
            else:
                parent[key] = unicode(json_format_datetime(
                    matching_datetime.replace(tzinfo=None)))

    elif isinstance(data, dict):
        for key, value in data.items():
            adjust_datetimes(value, parent=data, key=key)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            adjust_datetimes(value, parent=data, key=i)

    # return data, just for convenience in testing
    # this is the original input, modified, not a new data structure
    return data


def _extract_meta_instance_id(form):
    """Takes form json (as returned by xml2json)"""
    if form.get('Meta'):
        # bhoma, 0.9 commcare
        meta = form['Meta']
    elif form.get('meta'):
        # commcare 1.0
        meta = form['meta']
    else:
        return None

    if meta.get('uid'):
        # bhoma
        return meta['uid']
    elif meta.get('instanceID'):
        # commcare 0.9, commcare 1.0
        return meta['instanceID']
    else:
        return None


