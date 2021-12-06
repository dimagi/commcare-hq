import datetime
import uuid
from xml.etree import cElementTree as ElementTree

from django.template.loader import render_to_string

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import property_changed_in_action
from corehq.apps.es.cases import CaseES
from corehq.apps.es import filters
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.form_processor.exceptions import (
    CaseNotFound,
    MissingFormXml,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

CASEBLOCK_CHUNKSIZE = 100
SYSTEM_FORM_XMLNS = 'http://commcarehq.org/case'
EDIT_FORM_XMLNS = 'http://commcarehq.org/case/edit'

SYSTEM_FORM_XMLNS_MAP = {
    SYSTEM_FORM_XMLNS: 'System Form',
    EDIT_FORM_XMLNS: 'Data Cleaning Form',
}

ALLOWED_CASE_IDENTIFIER_TYPES = [
    "contact_phone_number",
    "external_id",
]


def submit_case_blocks(case_blocks, domain, username="system", user_id=None,
                       xmlns=None, attachments=None, form_id=None,
                       form_extras=None, case_db=None, device_id=None, max_wait=...):
    """
    Submits casexml in a manner similar to how they would be submitted from a phone.

    :param xmlns: Form XMLNS. Format: IRI or URN. Historically this was
    used in some places to uniquely identify the subsystem that posted
    the cases; `device_id` is now recommended for that purpose. Going
    forward, it is recommended to use the default value along with
    `device_id`, which indicates that the cases were submitted by an
    internal system process.
    :param device_id: Identifier for the source of posted cases. Ideally
    this should uniquely identify the subsystem that is posting cases to
    make it easier to trace the source. All new code should use this
    argument. A human recognizable value is recommended outside of test
    code. Example: "auto-close-rule-<GUID>"
    :param max_wait: Maximum time (in seconds) to allow the process to be delayed if
    the project is over its submission rate limit.
    See the docstring for submit_form_locally for meaning of values.

    returns the UID of the resulting form.
    """
    attachments = attachments or {}
    now = json_format_datetime(datetime.datetime.utcnow())
    if not isinstance(case_blocks, str):
        case_blocks = ''.join(case_blocks)
    form_id = form_id or uuid.uuid4().hex
    form_xml = render_to_string('hqcase/xml/case_block.xml', {
        'xmlns': xmlns or SYSTEM_FORM_XMLNS,
        'case_block': case_blocks,
        'time': now,
        'uid': form_id,
        'username': username,
        'user_id': user_id or "",
        'device_id': device_id or "",
    })
    form_extras = form_extras or {}

    result = submit_form_locally(
        instance=form_xml,
        domain=domain,
        attachments=attachments,
        case_db=case_db,
        max_wait=max_wait,
        **form_extras
    )
    return result.xform, result.cases


def get_case_by_identifier(domain, identifier):

    case_accessors = CaseAccessors(domain)

    # Try by any of the allowed identifiers
    for identifier_type in ALLOWED_CASE_IDENTIFIER_TYPES:
        result = CaseES().domain(domain).filter(
            filters.term(identifier_type, identifier)).get_ids()
        if result:
            return case_accessors.get_case(result[0])
    # Try by case id
    try:
        case_by_id = case_accessors.get_case(identifier)
        if case_by_id.domain == domain:
            return case_by_id
    except (CaseNotFound, KeyError):
        pass

    return None


def submit_case_block_from_template(domain, template, context, xmlns=None,
        user_id=None, device_id=None):
    case_block = render_to_string(template, context)
    # Ensure the XML is formatted properly
    # An exception is raised if not
    case_block = ElementTree.tostring(ElementTree.XML(case_block), encoding='utf-8').decode('utf-8')

    return submit_case_blocks(
        case_block,
        domain,
        user_id=user_id or SYSTEM_USER_ID,
        xmlns=xmlns,
        device_id=device_id,
    )


def _get_update_or_close_case_block(case_id, case_properties=None, close=False, owner_id=None):
    kwargs = {
        'create': False,
        'user_id': SYSTEM_USER_ID,
        'close': close,
    }
    if case_properties:
        kwargs['update'] = case_properties
    if owner_id:
        kwargs['owner_id'] = owner_id

    return CaseBlock.deprecated_init(case_id, **kwargs)


def update_case(domain, case_id, case_properties=None, close=False,
                xmlns=None, device_id=None, owner_id=None):
    """
    Updates or closes a case (or both) by submitting a form.
    domain - the case's domain
    case_id - the case's id
    case_properties - to update the case, pass in a dictionary of {name1: value1, ...}
                      to ignore case updates, leave this argument out
    close - True to close the case, False otherwise
    xmlns - pass in an xmlns to use it instead of the default
    device_id - see submit_case_blocks device_id docs
    """
    caseblock = _get_update_or_close_case_block(case_id, case_properties, close, owner_id)
    return submit_case_blocks(
        ElementTree.tostring(caseblock.as_xml(), encoding='utf-8').decode('utf-8'),
        domain,
        user_id=SYSTEM_USER_ID,
        xmlns=xmlns,
        device_id=device_id,
    )


def bulk_update_cases(domain, case_changes, device_id, xmlns=None):
    """
    Updates or closes a list of cases (or both) by submitting a form.
    domain - the cases' domain
    case_changes - a tuple in the form (case_id, case_properties, close)
        case_id - id of the case to update
        case_properties - to update the case, pass in a dictionary of {name1: value1, ...}
                          to ignore case updates, leave this argument out
        close - True to close the case, False otherwise
    device_id - see submit_case_blocks device_id docs
    """
    case_blocks = []
    for case_id, case_properties, close in case_changes:
        case_block = _get_update_or_close_case_block(case_id, case_properties, close)
        case_blocks.append(case_block.as_text())
    return submit_case_blocks(case_blocks, domain, device_id=device_id, xmlns=xmlns)


def resave_case(domain, case, send_post_save_signal=True):
    from corehq.form_processor.change_publishers import publish_case_saved
    publish_case_saved(case, send_post_save_signal)


def get_last_non_blank_value(case, case_property):
    case_transactions = sorted(case.actions, key=lambda t: t.server_date, reverse=True)
    for case_transaction in case_transactions:
        try:
            property_changed_info = property_changed_in_action(
                case.domain,
                case_transaction,
                case.case_id,
                case_property
            )
        except MissingFormXml:
            property_changed_info = None
        if property_changed_info and property_changed_info.new_value:
            return property_changed_info.new_value
