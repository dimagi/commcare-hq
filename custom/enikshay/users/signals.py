from corehq import toggles
from corehq.apps.users.signals import clean_commcare_user
from .setup_utils import get_allowable_usertypes, get_user_role


def user_save_callback(sender, domain, user, forms, **kwargs):
    if (not toggles.ENIKSHAY.enabled(domain)
            or not user.is_commcare_user()):
        return

    user_form = forms.get('UpdateCommCareUserInfoForm')
    custom_data = forms.get('CustomDataEditor')
    if not user_form and custom_data:
        raise AssertionError("Expected user form and custom data form to be submitted")

    allowed_usertypes = get_allowable_usertypes(domain, user)
    if custom_data.form.cleaned_data['usertype'] not in allowed_usertypes:
        custom_data.form.add_error(
            'usertype',
            "'User Type' must be one of the following: {}".format(', '.join(allowed_usertypes))
        )

    # role = get_user_role(domain, user)
    # if role and :
    # user.set_role(domain, role_id)  # 'user-role:'


def connect_signals():
    clean_commcare_user.connect(user_save_callback, dispatch_uid="user_save_callback")
