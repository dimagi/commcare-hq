from __future__ import absolute_import
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
import uuid
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_domain_hq_user_id
from couchdbkit.exceptions import MultipleResultsFound
from corehq.elastic import es_query


class FakeSyncOp(object):
    """
    Fake version of CaseSyncOperation useful for testing
    """
    def __init__(self, cases):
        self.actual_owned_cases = cases


def sync_user_cases(commcare_user):
    """
    Each time a CommCareUser is saved this method gets called and creates or updates
    a case associated with the user with the user's details.
    """
    domain = commcare_user.project
    if not (domain and domain.call_center_config.enabled):
        return

    def valid_element_name(name):
        try:
            ElementTree.fromstring('<{}/>'.format(name))
            return True
        except ElementTree.ParseError:
            return False

    # remove any keys that aren't valid XML element names
    fields = {k: v for k, v in commcare_user.user_data.items() if valid_element_name(k)}

    # language or phone_number can be null and will break
    # case submission
    fields.update({
        'name': commcare_user.name or commcare_user.raw_username,
        'username': commcare_user.raw_username,
        'email': commcare_user.email,
        'language': commcare_user.language or '',
        'phone_number': commcare_user.phone_number or ''
    })

    try:
        case = get_case_by_domain_hq_user_id(domain.name, commcare_user._id, include_docs=True)
        found = bool(case)
    except MultipleResultsFound:
        return

    close = commcare_user.to_be_deleted() or not commcare_user.is_active

    owner_id = domain.call_center_config.case_owner_id
    caseblock = None
    if found:
        props = dict(case.dynamic_case_properties())

        changed = close != case.closed
        changed = changed or case.type != domain.call_center_config.case_type
        changed = changed or case.name != fields['name']

        if not changed:
            for field, value in fields.items():
                if field != 'name' and props.get(field) != value:
                    changed = True
                    break

        if changed:
            caseblock = CaseBlock(
                create=False,
                case_id=case._id,
                version=V2,
                case_type=domain.call_center_config.case_type,
                close=close,
                update=fields
            )
    else:
        fields['hq_user_id'] = commcare_user._id
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=owner_id,
            user_id=owner_id,
            version=V2,
            case_type=domain.call_center_config.case_type,
            update=fields
        )

    if caseblock:
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, domain.name)


def get_call_center_domains():
    q = {'fields': ['name']}
    result = es_query(params={
        'internal.using_call_center': True,
        'is_active': True,
        'is_snapshot': False
    }, q=q)
    hits = result.get('hits', {}).get('hits', {})
    return [hit['fields']['name'] for hit in hits]
