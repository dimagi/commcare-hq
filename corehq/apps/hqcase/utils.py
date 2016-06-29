import datetime
import uuid
from xml.etree import ElementTree
import xml.etree.ElementTree as ET
import re

from django.core.files.uploadedfile import UploadedFile
from django.template.loader import render_to_string

from casexml.apps.phone.xml import get_case_xml
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import get_cached_case_attachment, CaseAccessors
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.phone.caselogic import get_related_cases
from corehq.apps.hqcase.exceptions import CaseAssignmentError
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.users.util import SYSTEM_USER_ID
from casexml.apps.case import const

SYSTEM_FORM_XMLNS = 'http://commcarehq.org/case'

ALLOWED_CASE_IDENTIFIER_TYPES = [
    "contact_phone_number",
    "external_id",
]


def submit_case_blocks(case_blocks, domain, username="system", user_id="",
                       xmlns=SYSTEM_FORM_XMLNS, attachments=None,
                       form_id=None):
    """
    Submits casexml in a manner similar to how they would be submitted from a phone.

    returns the UID of the resulting form.
    """
    attachments = attachments or {}
    now = json_format_datetime(datetime.datetime.utcnow())
    if not isinstance(case_blocks, basestring):
        case_blocks = ''.join(case_blocks)
    form_id = form_id or uuid.uuid4().hex
    form_xml = render_to_string('hqcase/xml/case_block.xml', {
        'xmlns': xmlns,
        'case_block': case_blocks,
        'time': now,
        'uid': form_id,
        'username': username,
        'user_id': user_id,
    })
    response, xform, cases = submit_form_locally(
        instance=form_xml,
        domain=domain,
        attachments=attachments,
    )
    return xform


def get_case_wrapper(data):
    from corehq.apps.commtrack.util import get_case_wrapper as commtrack_wrapper

    def pact_wrapper(data):
        if data['domain'] == 'pact' and data['type'] == 'cc_path_client':
            from pact.models import PactPatientCase
            return PactPatientCase

    wrapper_funcs = [pact_wrapper, commtrack_wrapper]

    wrapper = None
    for wf in wrapper_funcs:
        wrapper = wf(data)
        if wrapper is not None:
            break
    return wrapper


def _get_cases_by_domain_hq_user_id(domain, user_id, case_type, include_docs):
    return CommCareCase.view(
        'case_by_domain_hq_user_id_type/view',
        key=[domain, user_id, case_type],
        reduce=False,
        include_docs=include_docs
    ).all()


def get_case_by_domain_hq_user_id(domain, user_id, case_type):
    """
    Return the first case of case_type owned by user_id
    """
    cases = _get_cases_by_domain_hq_user_id(domain, user_id, case_type, include_docs=True)
    return cases[0] if cases else None


def get_case_id_by_domain_hq_user_id(domain, user_id, case_type):
    """
    Return the ID of the first case of case_type owned by user_id
    """
    rows = _get_cases_by_domain_hq_user_id(domain, user_id, case_type, include_docs=False)
    return rows[0]['id'] if rows else None


def get_case_by_identifier(domain, identifier):
    # circular import
    from corehq.apps.api.es import CaseES
    case_es = CaseES(domain)
    case_accessors = CaseAccessors(domain)

    def _query_by_type(i_type):
        q = case_es.base_query(
            terms={
                i_type: identifier,
            },
            fields=['_id', i_type],
            size=1
        )
        response = case_es.run_query(q)
        raw_docs = response['hits']['hits']
        if raw_docs:
            return case_accessors.get_case(raw_docs[0]['_id'])

    # Try by any of the allowed identifiers
    for identifier_type in ALLOWED_CASE_IDENTIFIER_TYPES:
        case = _query_by_type(identifier_type)
        if case is not None:
            return case

    # Try by case id
    try:
        case_by_id = case_accessors.get_case(identifier)
        if case_by_id.domain == domain:
            return case_by_id
    except (CaseNotFound, KeyError):
        pass

    return None


def assign_case(case_or_case_id, owner_id, acting_user=None, include_subcases=True,
                include_parent_cases=False, exclude_function=None, update=None):
    """
    Assigns a case to an owner. Optionally traverses through subcases and parent cases
    and reassigns those to the same owner.
    """
    if isinstance(case_or_case_id, basestring):
        primary_case = CommCareCase.get(case_or_case_id)
    else:
        primary_case = case_or_case_id
    cases_to_assign = [primary_case]
    if include_subcases:
        cases_to_assign.extend(get_related_cases([primary_case], primary_case.domain, search_up=False).values())
    if include_parent_cases:
        cases_to_assign.extend(get_related_cases([primary_case], primary_case.domain, search_up=True).values())
    if exclude_function:
        cases_to_assign = [c for c in cases_to_assign if not exclude_function(c)]
    return assign_cases(cases_to_assign, owner_id, acting_user, update=update)


def assign_cases(caselist, owner_id, acting_user=None, update=None):
    """
    Assign all cases in a list to an owner. Won't update if the owner is already
    set on the case. Doesn't touch parent cases or subcases.

    Returns the list of ids of cases that were reassigned.
    """
    if not caselist:
        return

    def _assert(bool, msg):
        if not bool:
            raise CaseAssignmentError(msg)

    from corehq.apps.users.cases import get_wrapped_owner
    # "security"
    unique_domains = set([c.domain for c in caselist])
    _assert(len(unique_domains) == 1, 'case list had cases spanning multiple domains')
    [domain] = unique_domains
    _assert(domain, 'domain for cases was empty')
    owner = get_wrapped_owner(owner_id)
    _assert(owner, 'no owner with id "%s" found' % owner_id)
    _assert(owner.domain == domain, 'owner was not in domain %s for cases' % domain)

    username = acting_user.username if acting_user else 'system'
    user_id = acting_user._id if acting_user else 'system'
    filtered_cases = set([c for c in caselist if c.owner_id != owner_id])
    if filtered_cases:
        caseblocks = [ElementTree.tostring(CaseBlock(
                create=False,
                case_id=c.case_id,
                owner_id=owner_id,
                update=update,
            ).as_xml()) for c in filtered_cases
        ]
        # todo: this should check whether the submit_case_blocks call actually succeeds
        submit_case_blocks(caseblocks, domain, username=username,
                           user_id=user_id)

    return [c._id for c in filtered_cases]


def make_creating_casexml(domain, case, new_case_id, new_parent_ids=None):
    new_parent_ids = new_parent_ids or {}
    old_case_id = case.case_id
    case.case_id = new_case_id
    local_move_back = {}
    for index in case.indices:
        new = new_parent_ids[index.referenced_id]
        old = index.referenced_id
        local_move_back[new] = old
        index.referenced_id = new
    try:
        case_block = get_case_xml(case, (const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE), version='2.0')
        case_block, attachments = _process_case_block(domain, case_block, case.case_attachments, old_case_id)
    finally:
        case.case_id = old_case_id
        for index in case.indices:
            index.referenced_id = local_move_back[index.referenced_id]
    return case_block, attachments


def _process_case_block(domain, case_block, attachments, old_case_id):
    def get_namespace(element):
        m = re.match('\{.*\}', element.tag)
        return m.group(0)[1:-1] if m else ''

    def local_attachment(attachment, old_case_id, tag):
        mime = attachment['server_mime']
        size = attachment['attachment_size']
        src = attachment['attachment_src']
        cached_attachment = get_cached_case_attachment(domain, old_case_id, tag)
        attachment_meta, attachment_stream = cached_attachment.get()
        return UploadedFile(attachment_stream, src, size=size, content_type=mime)

    # Remove namespace because it makes looking up tags a pain
    root = ET.fromstring(case_block)
    xmlns = get_namespace(root)
    case_block = re.sub(' xmlns="[^"]+"', '', case_block, count=1)

    root = ET.fromstring(case_block)
    tag = "attachment"
    xml_attachments = root.find(tag)
    ret_attachments = {}

    if xml_attachments:
        for attach in xml_attachments:
            attach.attrib['from'] = 'local'
            attach.attrib['src'] = attachments[attach.tag]['attachment_src']
            ret_attachments[attach.attrib['src']] = local_attachment(attachments[attach.tag], old_case_id, attach.tag)

    # Add namespace back in without { } added by ET
    root.attrib['xmlns'] = xmlns
    return ET.tostring(root), ret_attachments


def submit_case_block_from_template(domain, template, context, xmlns=None, user_id=None):
    case_block = render_to_string(template, context)
    # Ensure the XML is formatted properly
    # An exception is raised if not
    case_block = ElementTree.tostring(ElementTree.XML(case_block))

    user_id = user_id or SYSTEM_USER_ID
    kwargs = {}
    if xmlns:
        kwargs['xmlns'] = xmlns
    submit_case_blocks(case_block, domain, user_id=user_id, **kwargs)


def update_case(domain, case_id, case_properties=None, close=False, xmlns=None):
    """
    Updates or closes a case (or both) by submitting a form.
    domain - the case's domain
    case_id - the case's id
    case_properties - to update the case, pass in a dictionary of {name1: value1, ...}
                      to ignore case updates, leave this argument out
    close - True to close the case, False otherwise
    xmlns - pass in an xmlns to use it instead of the default
    """
    context = {
        'case_id': case_id,
        'date_modified': json_format_datetime(datetime.datetime.utcnow()),
        'user_id': SYSTEM_USER_ID,
        'case_properties': case_properties,
        'close': close,
    }
    submit_case_block_from_template(domain, 'hqcase/xml/update_case.xml', context, xmlns=xmlns)
