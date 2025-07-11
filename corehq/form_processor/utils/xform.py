from datetime import datetime
from lxml import etree
import re

import iso8601
import pytz

import xml2json
from corehq.form_processor.interfaces.processor import XFormQuestionValueIterator
from corehq.form_processor.models import Attachment, XFormInstance
from corehq.form_processor.exceptions import XFormQuestionValueNotFound
from corehq.toggles import CONVERT_XML_GROUP_SEPARATOR
from dimagi.ext import jsonobject
from dimagi.utils.parsing import json_format_datetime

# The functionality below to create a simple wrapped XForm is used in production code (repeaters) and so is
# not in the test utils
SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    {form_properties}
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>{device_id}</n1:deviceID>
        <n1:timeStart>{time_start}</n1:timeStart>
        <n1:timeEnd>{time_end}</n1:timeEnd>
        <n1:username>{username}</n1:username>
        <n1:userID>{user_id}</n1:userID>
        <n1:instanceID>{uuid}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms"></n2:appVersion>
    </n1:meta>
    {case_block}
</data>"""


# this is like jsonobject.api.re_datetime,
# but without the "time" parts being optional
# i.e. I just removed (...)? surrounding the second two lines
# This is used to in our form processor so we detect what strings are datetimes.
RE_DATETIME_MATCH = re.compile(r"""
    ^
    (\d{4})  # year
    \D?
    (0[1-9]|1[0-2])  # month
    \D?
    ([12]\d|0[1-9]|3[01])  # day
    [ T]
    ([01]\d|2[0-3])  # hour
    \D?
    ([0-5]\d)  # minute
    \D?
    ([0-5]\d)?  # second
    \D?
    (\d{3,6})?  # millisecond
    ([zZ]|([\+-])([01]\d|2[0-3])\D?([0-5]\d)?)?  # timezone
    $
""", re.VERBOSE)


class TestFormMetadata(jsonobject.JsonObject):
    domain = jsonobject.StringProperty(required=False)
    xmlns = jsonobject.StringProperty(default='http://openrosa.org/formdesigner/form-processor')
    app_id = jsonobject.StringProperty(default='123')
    form_name = jsonobject.StringProperty(default='New Form')
    device_id = jsonobject.StringProperty(default='DEV IL')
    user_id = jsonobject.StringProperty(default='cruella_deville')
    username = jsonobject.StringProperty(default='eve')
    time_end = jsonobject.DateTimeProperty(default=datetime(2013, 4, 19, 16, 52, 2))
    time_start = jsonobject.DateTimeProperty(default=datetime(2013, 4, 19, 16, 53, 2))
    # Set this property to fake the submission time
    received_on = jsonobject.DateTimeProperty(default=datetime.utcnow)
    __test__ = False


class FormSubmissionBuilder(object):
    """
    Utility/helper object for building a form submission
    """

    def __init__(self, form_id, metadata=None, case_blocks=None, form_properties=None, form_template=SIMPLE_FORM):
        self.form_id = form_id
        self.metadata = metadata or TestFormMetadata()
        self.case_blocks = case_blocks or []
        self.form_template = form_template
        self.form_properties = form_properties or {}

    def as_xml_string(self):
        case_block_xml = ''.join(cb.as_text() for cb in self.case_blocks)
        form_properties_xml = build_form_xml_from_property_dict(self.form_properties)
        form_xml = self.form_template.format(
            uuid=self.form_id, form_properties=form_properties_xml, case_block=case_block_xml,
            **self.metadata.to_json()
        )
        if not self.metadata.user_id:
            form_xml = form_xml.replace('<n1:userID>{}</n1:userID>'.format(self.metadata.user_id), '')
        return form_xml


def _build_node_list_from_dict(form_properties, separator=''):
    elements = []

    for key, values in form_properties.items():
        if not isinstance(values, list):
            values = [values]

        for value in values:
            node = etree.Element(key)
            if isinstance(value, dict):
                children = _build_node_list_from_dict(value, separator=separator)
                for child in children:
                    node.append(child)
            else:
                node.text = value
            elements.append(node)

    return elements


def build_form_xml_from_property_dict(form_properties, separator=''):
    return separator.join(
        etree.tostring(e, encoding='utf-8').decode('utf-8')
        for e in _build_node_list_from_dict(form_properties, separator)
    )


def get_simple_form_xml(form_id, case_id=None, metadata=None, simple_form=SIMPLE_FORM):
    from casexml.apps.case.mock import CaseBlock

    case_blocks = [CaseBlock(create=True, case_id=case_id)] if case_id else []
    return FormSubmissionBuilder(
        form_id=form_id,
        metadata=metadata,
        case_blocks=case_blocks,
        form_template=simple_form,
    ).as_xml_string()


def get_simple_wrapped_form(form_id, metadata=None, save=True, simple_form=SIMPLE_FORM):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface

    metadata = metadata or TestFormMetadata()
    xml = get_simple_form_xml(form_id=form_id, metadata=metadata, simple_form=simple_form)
    form_json = convert_xform_to_json(xml)
    interface = FormProcessorInterface(domain=metadata.domain)
    wrapped_form = interface.new_xform(form_json)
    wrapped_form.domain = metadata.domain
    wrapped_form.received_on = metadata.received_on
    interface.store_attachments(wrapped_form, [Attachment('form.xml', xml, 'text/xml')])
    if save:
        interface.save_processed_models([wrapped_form])
        wrapped_form = XFormInstance.objects.get_form(wrapped_form.form_id, metadata.domain)
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


def sanitize_instance_xml(xml_string, request):
    GROUP_SEPARATOR = b'&#29;'
    REPLACEMENT_CHARACTER = b'&#xFFFD;'
    if CONVERT_XML_GROUP_SEPARATOR.enabled_for_request(request):
        xml_string = xml_string.replace(GROUP_SEPARATOR, REPLACEMENT_CHARACTER)
    return xml_string


def convert_xform_to_json(xml_string):
    """
    takes xform payload as xml_string and returns the equivalent json
    i.e. the json that will show up as xform.form

    """

    try:
        name, json_form = xml2json.xml2json(xml_string)
    except xml2json.XMLSyntaxError as e:
        from couchforms import XMLSyntaxError
        raise XMLSyntaxError('Invalid XML: %s' % e)
    json_form['#type'] = name
    return json_form


def adjust_text_to_datetime(text):
    matching_datetime = iso8601.parse_date(text)
    return matching_datetime.astimezone(pytz.utc).replace(tzinfo=None)


def adjust_datetimes(data, parent=None, key=None):
    """
    find all datetime-like strings within data (deserialized json)
    and format them uniformly, in place.
    """
    # this strips the timezone like we've always done
    # todo: in the future this will convert to UTC
    if isinstance(data, str) and RE_DATETIME_MATCH.match(data):
        try:
            parent[key] = str(json_format_datetime(
                adjust_text_to_datetime(data)
            ))
        except (iso8601.ParseError, ValueError):
            pass
    elif isinstance(data, dict):
        for key, value in data.items():
            adjust_datetimes(value, parent=data, key=key)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            adjust_datetimes(value, parent=data, key=i)

    # return data, just for convenience in testing
    # this is the original input, modified, not a new data structure
    return data


def resave_form(domain, form):
    from corehq.form_processor.change_publishers import publish_form_saved
    publish_form_saved(form)


def get_node(root, question, xmlns=''):
    '''
    Given an xml element, find the node corresponding to a question path.
    See XFormQuestionValueIterator for question path format.
    Throws XFormQuestionValueNotFound if question is not present.
    '''

    def _next_node(node, xmlns, id, index=None):
        try:
            return node.findall("{{{}}}{}".format(xmlns, id))[index or 0]
        except (IndexError, KeyError):
            raise XFormQuestionValueNotFound()

    node = root
    i = XFormQuestionValueIterator(question)
    for (qid, index) in i:
        node = _next_node(node, xmlns, qid, index)
    node = _next_node(node, xmlns, i.last())
    if node is None:
        raise XFormQuestionValueNotFound()
    return node


def update_response(root, question, response, xmlns=None):
    '''
    Given a form submission's xml root, updates the response for an individual question.
    Question and response are both strings; see XFormQuestionValueIterator for question format.
    '''
    node = get_node(root, question, xmlns)
    if node.text != response:
        node.text = response
        return True
    return False
