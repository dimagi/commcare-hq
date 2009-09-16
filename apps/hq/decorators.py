from __future__ import absolute_import
from django.contrib.auth.decorators import user_passes_test
from hq.models import ExtUser

def extuser_required():
    """
    Decorator for views that checks whether a user is an extuser.
    Redirecting to the no permissions page if necessary.
    """
    def is_extuser(user):
        try:
            ExtUser.objects.get(id=user.id)
            return True
        except ExtUser.DoesNotExist:
            return False
    return user_passes_test(is_extuser, "/no_permissions")
