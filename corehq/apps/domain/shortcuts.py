"""
Shortcuts for working with domains and users.
"""


def create_domain(name, active=True):
    """Create domain without secure submissions for tests"""
    return Domain.get_or_create_with_name(name=name, is_active=active,
                                          secure_submissions=False)


def create_user(username, password, is_staff=False, is_superuser=False, is_active=True, is_ilsuser=False, **kwargs):
    user = User()
    user.username = username.lower()
    for key, val in kwargs.items():
        if key and val:
            setattr(user, key, val)
    user.is_staff = is_staff
    user.is_active = is_active
    user.is_superuser = is_superuser
    if not is_ilsuser:
        user.set_password(password)
    else:
        user.password = password

    user.save()
    return user

from corehq.apps.domain.models import Domain
from django.contrib.auth.models import User