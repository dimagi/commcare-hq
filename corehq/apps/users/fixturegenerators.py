"""
Generate user-based fixtures used in OTA restore
"""


def user_groups(user, version, case_sync_op=None, last_sync=None):
    """
    For a given user, return a fixture containing all the groups
    they are a part of.
    """
    fixture = user.get_group_fixture(last_sync)
    if fixture:
        return [fixture]
    else:
        return []
