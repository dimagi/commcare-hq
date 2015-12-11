import logging
from casexml.apps.case.signals import cases_received
from corehq.apps.hqcase.utils import assign_case
from custom.bihar import BIHAR_DOMAINS


SYSTEM_USERNAME = 'bihar-system'
SYSTEM_USERID = SYSTEM_USERNAME

DEMO_OWNER_IDS = set(['demo_user_group_id', 'demo_user_group_bihar'])
REASSIGN_BLACKLIST = ('anm_review', 'mcts_persona')


class BiharMockUser(object):
    username = SYSTEM_USERNAME
    _id = SYSTEM_USERID


def bihar_reassignment(sender, xform, cases, **kwargs):
    if hasattr(xform, 'domain') and xform.domain in BIHAR_DOMAINS and xform.metadata and xform.metadata.userID != SYSTEM_USERID:
        owner_ids = set(c.owner_id for c in cases)
        if len(owner_ids) != 1:
            logging.warning('form {form} had mismatched case owner ids'.format(form=xform._id))
        else:
            [owner_id] = owner_ids
            if owner_id not in DEMO_OWNER_IDS:
                # don't attempt to reassign the cases included in this form
                cases_not_to_touch = set(c._id for c in cases)
                def bihar_exclude(case):
                    return case._id in cases_not_to_touch or case.type in REASSIGN_BLACKLIST

                for case in cases:
                    if case.type in ('cc_bihar_pregnancy', 'cc_bihar_newborn'):
                        reassigned = assign_case(
                            case, owner_id, BiharMockUser(),
                            include_subcases=True, include_parent_cases=True,
                            exclude_function=bihar_exclude, update={'reassignment_form_id': xform._id}
                        )
                        # update the list of cases not to touch so we don't reassign the same
                        # cases multiple times in the same form
                        cases_not_to_touch = cases_not_to_touch | set(reassigned or [])


cases_received.connect(bihar_reassignment)
