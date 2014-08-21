"""
Generate user-based fixtures used in OTA restore
"""


def should_sync_groups(user, last_sync):
    """
    Determine if we need to sync the groups fixture by checking
    the modified date on all groups compared to the
    last sync.
    """
    if not last_sync or not last_sync.date:
        return True

    for group in user.get_case_sharing_groups():
        if not group.last_modified or group.last_modified >= last_sync.date:
            return True

    return False


def user_groups(user, version, last_sync):
    """
    For a given user, return a fixture containing all the groups
    they are a part of.
    """
    if not should_sync_groups(user, last_sync):
        return []
    return [user.get_group_fixture()]
