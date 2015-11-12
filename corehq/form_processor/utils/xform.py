import iso8601
import pytz
import xml2json

from redis.exceptions import RedisError
from dimagi.ext.jsonobject import re_loose_datetime
from dimagi.utils.couch import LockManager, ReleaseOnError
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.tzmigration import phone_timezones_should_be_processed
from couchforms.exceptions import DuplicateError

from ..models import Attachment


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


def new_xform(instance_xml, attachments=None, process=None):
    """
    create but do not save an XFormInstance from an xform payload (xml_string)
    optionally set the doc _id to a predefined value (_id)
    return doc _id of the created doc

    `process` is transformation to apply to the form right before saving
    This is to avoid having to save multiple times

    If xml_string is bad xml
      - raise couchforms.XMLSyntaxError

    """
    from corehq.form_processor.interfaces.processor import FormProcessorInterface

    assert attachments is not None
    form_data = convert_xform_to_json(instance_xml)
    adjust_datetimes(form_data)

    xform = FormProcessorInterface().new_xform(form_data)

    # Maps all attachments to uniform format and adds form.xml to list before storing
    attachments = map(
        lambda a: Attachment(name=a[0], content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachments.append(Attachment(name='form.xml', content=instance_xml, content_type='text/xml'))
    FormProcessorInterface().store_attachments(xform, attachments)

    # this had better not fail, don't think it ever has
    # if it does, nothing's saved and we get a 500
    if process:
        process(xform)

    lock = acquire_lock_for_xform(xform.form_id)
    with ReleaseOnError(lock):
        if FormProcessorInterface().is_duplicate(xform):
            raise DuplicateError(xform)

    return LockManager(xform, lock)


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


def acquire_lock_for_xform(xform_id):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface

    # this is high, but I want to test if MVP conflicts disappear
    lock = FormProcessorInterface().xform_model.get_obj_lock_by_id(xform_id, timeout_seconds=2 * 60)
    try:
        lock.acquire()
    except RedisError:
        lock = None
    return lock
