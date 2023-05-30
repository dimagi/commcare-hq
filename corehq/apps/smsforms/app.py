import re
from xml.etree.cElementTree import XML, tostring

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.util import get_cloudcare_session_data
from corehq.apps.cloudcare.touchforms_api import CaseSessionDataHelper
from corehq.apps.formplayer_api.smsforms import sms as tfsms
from corehq.apps.formplayer_api.smsforms.api import (
    FormplayerInterface,
    InvalidSessionIdException,
    TouchformsError,
    XFormsConfig,
)
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling.util import utcnow

from .models import SQLXFormsSession

COMMCONNECT_DEVICE_ID = "commconnect"


def start_session(session, domain, contact, app, form, case_id=None, yield_responses=False):
    """
    Starts a session in touchforms and saves the record in the database.
    
    Returns a tuple containing the session object and the (text-only) 
    list of generated questions/responses based on the form.
    
    Special params:
    yield_responses - If True, the list of xforms responses is returned, otherwise the text prompt for each is returned
    """
    # NOTE: this call assumes that "contact" will expose three
    # properties: .raw_username, .get_id, and .get_language_code
    session_data = CaseSessionDataHelper(domain, contact, case_id, app, form).get_session_data(
        COMMCONNECT_DEVICE_ID)

    kwargs = {}
    if is_commcarecase(contact):
        kwargs['restore_as_case_id'] = contact.case_id
    else:
        kwargs['restore_as'] = contact.raw_username

    if app and form:
        session_data.update(get_cloudcare_session_data(domain, form, contact))

    language = contact.get_language_code()
    config = XFormsConfig(form_content=form.render_xform().decode('utf-8'),
                          language=language,
                          session_data=session_data,
                          domain=domain,
                          **kwargs)

    session_start_info = tfsms.start_session(config)
    session.session_id = session_start_info.session_id
    session.save()
    responses = session_start_info.first_responses

    if len(responses) > 0 and responses[0].status == 'http-error':
        session.mark_completed(False)
        raise TouchformsError('Cannot connect to touchforms.')

    # Prevent future update conflicts by getting the session again from the db
    # since the session could have been updated separately in the first_responses call
    session = SQLXFormsSession.objects.get(pk=session.pk)
    if yield_responses:
        return (session, responses)
    else:
        return (session, _responses_to_text(responses))


def get_responses(domain, session_id, text):
    """
    Try to process this message like a session-based submission against
    an xform.
    
    Returns a list of responses if there are any.
    """
    return list(tfsms.next_responses(session_id, text, domain))


def _responses_to_text(responses):
    return [r.text_prompt for r in responses if r.text_prompt]


def get_events_from_responses(responses):
    return [r.event for r in responses if r.event]


def submit_unfinished_form(session):
    """
    Gets the raw instance of the session's form and submits it. This is used with
    sms and ivr surveys to save all questions answered so far in a session that
    needs to close.

    If session.include_case_updates_in_partial_submissions is False, no case
    create / update / close actions will be performed, but the form will still be submitted.

    The form is only submitted if the smsforms session has not yet completed.
    """
    formplayer_interface = FormplayerInterface(session.session_id, session.domain)
    try:
        xml = _fetch_xml(formplayer_interface)
    except InvalidSessionIdException:
        return

    remove_case_actions = not session.include_case_updates_in_partial_submissions
    cleaned_xml = _clean_xml_for_partial_submission(xml, should_remove_case_actions=remove_case_actions)

    result = submit_form_locally(cleaned_xml, session.domain, app_id=session.app_id, partial_submission=True)
    session.submission_id = result.xform.form_id


def _fetch_xml(formplayer_interface):
    """
    :param formplayer_interface: FormplayerInterface obj
    :return: serialized instance xml with relevant nodes only
    """
    response = formplayer_interface.get_raw_instance()
    # Formplayer's ExceptionResponseBean includes the exception message,
    # status ("error"), url, and type ("text")
    if response.get('status') == 'error':
        raise TouchformsError(response.get('exception'))
    return response['output']


def _clean_xml_for_partial_submission(xml, should_remove_case_actions):
    """
    Helper method to cleanup partially completed xml for submission
    :param xml: partially completed xml
    :param should_remove_case_actions: if True, remove case actions (create, update, close) from xml
    :return: byte str of cleaned xml
    """
    root = XML(xml)
    case_tag_regex = re.compile(r"^(\{.*\}){0,1}case$") # Use regex in order to search regardless of namespace
    meta_tag_regex = re.compile(r"^(\{.*\}){0,1}meta$")
    timeEnd_tag_regex = re.compile(r"^(\{.*\}){0,1}timeEnd$")
    current_timestamp = json_format_datetime(utcnow())
    for child in root:
        if case_tag_regex.match(child.tag) is not None:
            # Found the case tag
            case_element = child
            case_element.set("date_modified", current_timestamp)
            if should_remove_case_actions:
                child_elements = [case_action for case_action in case_element]
                for case_action in child_elements:
                    case_element.remove(case_action)
        elif meta_tag_regex.match(child.tag) is not None:
            # Found the meta tag, now set the value for timeEnd
            for meta_child in child:
                if timeEnd_tag_regex.match(meta_child.tag):
                    meta_child.text = current_timestamp
    return tostring(root)
