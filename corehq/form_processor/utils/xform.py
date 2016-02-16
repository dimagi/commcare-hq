import iso8601
import pytz
import xml2json
from datetime import datetime

from dimagi.ext import jsonobject
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.tzmigration import phone_timezones_should_be_processed
from corehq.form_processor.models import Attachment


# The functionality below to create a simple wrapped XForm is used in production code (repeaters) and so is
# not in the test utils
SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    <dalmation_count>yes</dalmation_count>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>DEV IL</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>{time_end}</n1:timeEnd>
        <n1:username>eve</n1:username>
        <n1:userID>{user_id}</n1:userID>
        <n1:instanceID>{uuid}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms"></n2:appVersion>
    </n1:meta>
    {case_block}
</data>"""


class TestFormMetadata(jsonobject.JsonObject):
    domain = jsonobject.StringProperty(required=False)
    xmlns = jsonobject.StringProperty(default='http://openrosa.org/formdesigner/form-processor')
    app_id = jsonobject.StringProperty(default='123')
    form_name = jsonobject.StringProperty(default='New Form')
    user_id = jsonobject.StringProperty(default='cruella_deville')
    time_end = jsonobject.DateTimeProperty(default=datetime(2013, 4, 19, 16, 53, 2))
    # Set this property to fake the submission time
    received_on = jsonobject.DateTimeProperty(default=datetime.utcnow)


def get_simple_form_xml(form_id, case_id=None, metadata=None):
    from casexml.apps.case.mock import CaseBlock

    metadata = metadata or TestFormMetadata()
    case_block = ''
    if case_id:
        case_block = CaseBlock(create=True, case_id=case_id).as_string()
    form_xml = SIMPLE_FORM.format(uuid=form_id, case_block=case_block, **metadata.to_json())
    return form_xml


def get_simple_wrapped_form(form_id, case_id=None, metadata=None, save=True):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface

    xml = get_simple_form_xml(form_id=form_id, metadata=metadata)
    form_json = convert_xform_to_json(xml)
    interface = FormProcessorInterface(domain=metadata.domain)
    wrapped_form = interface.new_xform(form_json)
    wrapped_form.domain = metadata.domain
    interface.store_attachments(wrapped_form, [Attachment('form.xml', xml, 'text/xml')])
    if save:
        interface.save_processed_models([wrapped_form])

    return wrapped_form


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
    if isinstance(data, basestring) and jsonobject.re_loose_datetime.match(data):
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
