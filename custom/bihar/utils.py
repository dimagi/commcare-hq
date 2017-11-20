from __future__ import absolute_import
import itertools
import logging
from xml.etree import cElementTree as ElementTree

from django.utils.translation import ugettext_noop

from custom.bihar.exceptions import CaseAssignmentError
from casexml.apps.case.dbaccessors import get_reverse_indices_json
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.processor import FormProcessorInterface
import six

ASHA_ROLE = ugettext_noop('ASHA')
AWW_ROLE = ugettext_noop('AWW')
ANM_ROLE = ugettext_noop('ANM')
LS_ROLE = ugettext_noop('LS')

FLW_ROLES = (ASHA_ROLE, AWW_ROLE)
SUPERVISOR_ROLES = (ANM_ROLE, LS_ROLE)


def get_role(user):
    return (user.user_data.get('role') or '').upper()


def get_team_members(group, roles=FLW_ROLES):
    """
    Get any commcare users that are either "asha" or "aww".
    """
    users = group.get_users(only_commcare=True)
    return sorted([u for u in users if get_role(u) in roles],
                  key=lambda u: u.user_data['role'].upper())


def groups_for_user(user, domain):
    if user.is_commcare_user():
        return Group.by_user(user)
    else:
        # for web users just show everything?
        return Group.by_domain(domain)


def get_all_owner_ids(user_ids):
    all_group_ids = [
        row['id']
        for row in Group.get_db().view(
            'groups/by_user',
            keys=user_ids,
            include_docs=False
        )
    ]
    return set(user_ids).union(set(all_group_ids))


def get_all_owner_ids_from_group(group):
    return get_all_owner_ids([user.get_id for user in get_team_members(group)])


def assign_case(case_or_case_id, owner_id, acting_user=None, include_subcases=True,
                include_parent_cases=False, exclude_function=None, update=None):
    """
    Assigns a case to an owner. Optionally traverses through subcases and parent cases
    and reassigns those to the same owner.
    """
    if isinstance(case_or_case_id, six.string_types):
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
        device_id = __name__ + ".assign_cases"
        submit_case_blocks(caseblocks, domain, username=username,
                           user_id=user_id, device_id=device_id)

    return [c._id for c in filtered_cases]


def get_related_cases(initial_cases, domain, strip_history=False, search_up=True):
    """
    Gets the flat list of related cases based on a starting list.
    Walks all the referenced indexes recursively.
    If search_up is True, all cases and their parent cases are returned.
    If search_up is False, all cases and their child cases are returned.
    """
    if not initial_cases:
        return {}

    # infer whether to wrap or not based on whether the initial list is wrapped or not
    # initial_cases may be a list or a set
    wrap = isinstance(next(iter(initial_cases)), CommCareCase)

    # todo: should assert that domain exists here but this breaks tests
    case_db = FormProcessorInterface(domain).casedb_cache(
        domain=domain,
        strip_history=strip_history,
        deleted_ok=True,
        wrap=wrap,
        initial=initial_cases
    )

    def indices(case):
        return case['indices'] if search_up else get_reverse_indices_json(domain, case['_id'])

    relevant_cases = {}
    relevant_deleted_case_ids = []

    cases_to_process = list(case for case in initial_cases)
    directly_referenced_indices = itertools.chain(
        *[[index['referenced_id'] for index in indices(case)]
          for case in initial_cases]
    )
    case_db.populate(directly_referenced_indices)

    def process_cases(cases):
        new_relations = set()
        for case in cases:
            if case and case['_id'] not in relevant_cases:
                relevant_cases[case['_id']] = case
                if case['doc_type'] == 'CommCareCase-Deleted':
                    relevant_deleted_case_ids.append(case['_id'])
                new_relations.update(index['referenced_id'] for index in indices(case))

        if new_relations:
            case_db.populate(new_relations)
            return [case_db.get(related_case) for related_case in new_relations]

    while cases_to_process:
        cases_to_process = process_cases(cases_to_process)

    if relevant_deleted_case_ids:
        logging.info('deleted cases included in footprint (restore): %s' % (
            ', '.join(relevant_deleted_case_ids)
        ))

    return relevant_cases
