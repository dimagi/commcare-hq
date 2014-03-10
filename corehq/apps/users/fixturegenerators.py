"""
Generate user-based fixtures used in OTA restore
"""


def user_groups(user, version, last_sync):
    """
    For a given user, return a fixture containing all the groups
    they are a part of.
    """
    return [user.get_group_fixture()]
