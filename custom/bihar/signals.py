import logging
from casexml.apps.case.signals import cases_received
from corehq.apps.hqcase.utils import assign_case
from custom.bihar import BIHAR_DOMAINS


SYSTEM_USERNAME = 'bihar-system'
SYSTEM_USERID = SYSTEM_USERNAME

DEMO_OWNER_IDS = set(['demo_user_group_id', 'demo_user_group_bihar'])

class BiharMockUser(object):
    username = SYSTEM_USERNAME
    _id = SYSTEM_USERID


def bihar_reassignment(sender, xform, cases, **kwargs):
    if xform.domain in BIHAR_DOMAINS and xform.metadata and xform.metadata.userID != SYSTEM_USERID:
        owner_ids = set(c.owner_id for c in cases)
        if len(owner_ids) != 1:
            logging.error('form {form} had mismatched case owner ids'.format(form=xform._id))
        else:
            [owner_id] = owner_ids
            if owner_id not in DEMO_OWNER_IDS:
                form_cases = set(c._id for c in cases)
                for case in cases:
                    if case.type in ('cc_bihar_pregnancy', 'cc_bihar_newborn'):
                        assign_case(case, owner_id, BiharMockUser(),
                                    include_subcases=True, include_parent_cases=True,
                                    exclude=form_cases)


cases_received.connect(bihar_reassignment)
