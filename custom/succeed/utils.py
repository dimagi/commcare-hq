from django.utils.translation import ugettext as _, ugettext_noop

SUCCEED_DOMAIN = 'succeed'
SUCCEED_CM_APPNAME = 'SUCCEED CM app'
SUCCEED_PM_APPNAME = 'SUCCEED PM app'
SUCCEED_CHW_APPNAME = 'SUCCEED CHW app'

CONFIG = {
    'groups': [
        dict(val="harbor", text=ugettext_noop("Harbor UCLA")),
        dict(val="lac-usc", text=ugettext_noop("LAC-USC")),
        dict(val="oliveview", text=ugettext_noop("Olive View Medical Center")),
        dict(val="rancho", text=ugettext_noop("Rancho Los Amigos")),
    ],
    'succeed_admin': 'SUCCEED Admin',
    'pm_role': 'PM',
    'pi_role': 'PI',
    'cm_role': 'CM',
    'chw_role': 'CHW'
}


def is_succeed_admin(user):
    return True if user.get_role()['name'] in [CONFIG['succeed_admin'], 'Admin'] else False


def is_pi(user):
    return True if 'user_data' in user and user.user_data['role'] in [CONFIG['pi_role']] else False


def is_cm(user):
    return True if 'user_data' in user and user.user_data['role'] in [CONFIG['cm_role']] else False


def is_chw(user):
    return True if 'user_data' in user and user.user_data['role'] in [CONFIG['chw_role']] else False


def is_pm_or_pi(user):
    return True if 'user_data' in user and user.user_data['role'] in [CONFIG['pm_role'], CONFIG['pi_role']] else False


def has_any_role(user):
    return True if 'user_data' in user and user.user_data['role'] in [CONFIG['pm_role'], CONFIG['pi_role'],
                                                                      CONFIG['cm_role'], CONFIG['chw_role']] else False


def get_form_dict(case, form_xmlns):
    forms = case.get_forms()
    for form in forms:
        form_dict = form.form
        if form_xmlns == form_dict["@xmlns"]:
            return form_dict
    return None