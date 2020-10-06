"""
Handles all superuser privileges
"""

def user_is_acting_as_superuser(request):
    return request.user.is_superuser
    