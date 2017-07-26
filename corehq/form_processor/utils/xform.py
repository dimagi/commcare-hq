from datetime import datetime

import iso8601
import pytz
from couchdbkit import ResourceNotFound

import xml2json
from corehq.apps.tzmigration.api import phone_timezones_should_be_processed
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import Attachment, XFormInstanceSQL
from dimagi.ext import jsonobject
from dimagi.utils.parsing import json_format_datetime

# The functionality below to create a simple wrapped XForm is used in production code (repeaters) and so is
# not in the test utils
SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="{form_name}" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="{xmlns}">
    <dalmation_count>yes</dalmation_count>
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


def get_simple_form_xml(form_id, case_id=None, metadata=None):
    from casexml.apps.case.mock import CaseBlock

    metadata = metadata or TestFormMetadata()
    case_block = ''
    if case_id:
        case_block = CaseBlock(create=True, case_id=case_id).as_string()
    form_xml = SIMPLE_FORM.format(uuid=form_id, case_block=case_block, **metadata.to_json())

    if not metadata.user_id:
        form_xml = form_xml.replace('<n1:userID>{}</n1:userID>'.format(metadata.user_id), '')

    return form_xml


def get_simple_wrapped_form(form_id, case_id=None, metadata=None, save=True):
    from corehq.form_processor.interfaces.processor import FormProcessorInterface

    metadata = metadata or TestFormMetadata()
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

    this only processes timezones correctly if the call comes from a request with domain information
    otherwise it will default to not processing timezones.

    to force timezone processing, it can be called as follows

    >>> from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
    >>> with force_phone_timezones_should_be_processed():
    >>>     adjust_datetimes(form_json)
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


def _get_form(form_id):
    from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
    from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
    try:
        return FormAccessorSQL.get_form(form_id)
    except XFormNotFound:
        pass

    try:
        return FormAccessorCouch.get_form(form_id)
    except ResourceNotFound:
        pass

    return None


def reprocess_xform_error_by_id(form_id, domain=None):
    form = _get_form(form_id)
    if domain and form.domain != domain:
        raise Exception('Form not found')
    return reprocess_xform_error(form)


def reprocess_xform_error(form):
    """
    Attempt to re-process an error form. This was created specifically to address
    the issue of out of order forms and child cases (form creates child case before
    parent case has been created).

    See http://manage.dimagi.com/default.asp?250459
    :param form_id: ID of the error form to process
    """
    from corehq.form_processor.interfaces.processor import FormProcessorInterface
    from corehq.form_processor.submission_post import SubmissionPost
    from corehq.form_processor.utils import should_use_sql_backend
    from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL
    from corehq.blobs.mixin import bulk_atomic_blobs
    from couchforms.models import XFormInstance
    from casexml.apps.case.signals import case_post_save
    from corehq.form_processor.interfaces.processor import ProcessedForms
    from corehq.form_processor.backends.sql.processor import FormProcessorSQL

    if not form:
        raise Exception('Form with ID {} not found'.format(form.form_id))

    if not form.is_error:
        raise Exception('Form was not an error form: {}={}'.format(form.form_id, form.doc_type))

    # reset form state prior to processing
    if should_use_sql_backend(form.domain):
        form.state = XFormInstanceSQL.NORMAL
    else:
        form.doc_type = 'XFormInstance'

    form.initial_processing_complete = True
    form.problem = None

    cache = FormProcessorInterface(form.domain).casedb_cache(
        domain=form.domain, lock=True, deleted_ok=True, xforms=[form]
    )
    with cache as casedb:
        case_stock_result = SubmissionPost.process_xforms_for_cases([form], casedb)

        if case_stock_result:
            stock_result = case_stock_result.stock_result
            if stock_result:
                assert stock_result.populated

            cases = case_stock_result.case_models
            if should_use_sql_backend(form.domain):
                for case in cases:
                    CaseAccessorSQL.save_case(case)

                if stock_result:
                    LedgerAccessorSQL.save_ledger_values(stock_result.models_to_save)

                FormAccessorSQL.update_form(form)
                FormProcessorSQL._publish_changes(
                    ProcessedForms(form, None),
                    cases,
                    stock_result
                )
            else:
                with bulk_atomic_blobs([form] + cases):
                    XFormInstance.save(form)  # use this save to that we don't overwrite the doc_type
                    XFormInstance.get_db().bulk_save(cases)
                if stock_result:
                    stock_result.commit()

            case_stock_result.stock_result.finalize()
            case_stock_result.case_result.commit_dirtiness_flags()

            for case in cases:
                case_post_save.send(case.__class__, case=case)

    return form
