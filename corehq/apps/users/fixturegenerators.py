from casexml.apps.case.xml import V1

'''
Generate user-based fixtures used in OTA restore
'''

def user_groups(user, version=V1, last_sync=None):
    """
    For a given user, return a fixture containing all the groups
    they are a part of.
    """
    assert(user._hq_user is not None) # HQ sets this on the casexml user
    return [user._hq_user.get_group_fixture()]