"""
Handles all superuser privileges
"""

def user_is_acting_as_superuser(request):
    # TODO: May need to deal with situations where it's request.couch_user vs request.user
    return request.user.is_superuser

def is_legacy_superuser(user):
    """Should be avoided if possible in favor of user_is_acting_as_superuser"""
    return user.is_superuser
    