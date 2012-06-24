"""
Shortcuts for working with domains and users.
"""

def create_domain(name, active=True):
    return Domain.get_or_create_with_name(name=name, is_active=active)

def create_user(username, password, is_staff=False, is_superuser=False, is_active=True, **kwargs):
    user = User()
    user.username = username.lower()
    for key, val in kwargs.items():
        if key and val:  setattr(user, key, val)
    user.is_staff = is_staff
    user.is_active = is_active
    user.is_superuser = is_superuser
    user.set_password(password)

    user.save()
    return user

def add_user_to_domain(user, domain):
    couch_user = user.get_profile().get_couch_user()
    couch_user.add_domain_membership(domain.name)
    couch_user.save()

from corehq.apps.domain.models import Domain
from django.contrib.auth.models import User