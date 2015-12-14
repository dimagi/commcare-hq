import iso8601
import pytz
import xml2json

from dimagi.ext.jsonobject import re_loose_datetime
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.tzmigration import phone_timezones_should_be_processed


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


def extract_meta_user_id(form):
    user_id = None
    if form.get('meta'):
        user_id = form.get('meta').get('userID', None)
    elif form.get('Meta'):
        user_id = form.get('Meta').get('user_id', None)
    return user_id


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
