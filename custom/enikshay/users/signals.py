from corehq.apps.users.signals import clean_commcare_user
from .setup_utils import get_allowable_usertypes


def user_save_callback(sender, form, **kwargs):
    domain = form.domain
    user = form.existing_user
    allowed_usertypes = get_allowable_usertypes(domain, user)
    if form.data['data-field-usertype'] not in allowed_usertypes:
        yield (None,
               "'User Type' must be one of the following: {}".format(', '.join(allowed_usertypes)))


def connect_signals():
    clean_commcare_user.connect(user_save_callback, dispatch_uid="user_save_callback")
