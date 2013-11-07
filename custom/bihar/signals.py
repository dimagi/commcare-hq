import logging
from casexml.apps.case.signals import cases_received
from corehq.apps.hqcase.utils import assign_case
from custom.bihar import BIHAR_DOMAINS


SYSTEM_USERNAME = 'bihar-system'
SYSTEM_USERID = SYSTEM_USERNAME

# hack: this is currently hardcoded to only work on a few trial groups
# for a soft launch ('bad case assignments', 'delhi', 'samda' and 'afrisis')

PREVIEW_GROUPS = set((
    'b5a5f0e68c699aef303b362b24de9406',
    '3c5a80e4db53049dfc110c368a0d53e1',
    '3c5a80e4db53049dfc110c368a0d45f0',
    '3c5a80e4db53049dfc110c368a0d44d9',
    '08f9605b21922239146f479b5cc59b3a',
    '70c6ba6f55ed21716fe725c2148932c2',
    '70c6ba6f55ed21716fe725c214892694',
    '70c6ba6f55ed21716fe725c21489335a',
    '8f5a275380f60fa6e54fd8b17eeb8e75',
    '8f5a275380f60fa6e54fd8b17eeb7ea0',
    '8f5a275380f60fa6e54fd8b17eeb7323',
    '8f5a275380f60fa6e54fd8b17eeb794e',
    '70c6ba6f55ed21716fe725c21489129c',
    '70c6ba6f55ed21716fe725c214892f9a',
    '70c6ba6f55ed21716fe725c214891dc4',
    'ac29755557888621b1e4285e7847b038',
    '3c5a80e4db53049dfc110c368a0d1570',
    '147a9298c8802885d629c0169bd6279d',
))

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
            if owner_id in PREVIEW_GROUPS:
                for case in cases:
                    if case.type in ('cc_bihar_pregnancy', 'cc_bihar_newborn'):
                        assign_case(case, owner_id, BiharMockUser(),
                                    include_subcases=True, include_parent_cases=True)


cases_received.connect(bihar_reassignment)
