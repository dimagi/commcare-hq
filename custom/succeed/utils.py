from couchdbkit.exceptions import ResourceNotFound
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.app_manager.models import Application

SUCCEED_DOMAIN = 'succeed'
SUCCEED_APPNAME = 'SUCCEED Project'

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


def _is_succeed_admin(user):
    return True if user.get_role()['name'] == CONFIG['succeed_admin'] else False


def _is_pm_or_pi(user):
    return True if 'role' in user.user_date and user.user_data['role'] in [CONFIG['pm_role'], CONFIG['pi_role']] else False


def _get_app_by_name(domain, name):
    app = Application.view('app_manager/applications_brief',
                                 startkey=[domain, name, {}],
                                 endkey=[domain, name],
                                 descending=True,
                                 limit=1).one()
    if app:
        return Application.get(app['_id'])
    else:
        raise ResourceNotFound(_("Not found application by name: %s") % name)
