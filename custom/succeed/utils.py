from django.utils.translation import ugettext_noop
from corehq.apps.app_manager.models import ApplicationBase

SUCCEED_DOMAIN = 'succeed'
SUCCEED_CLOUD_APPNAME = 'SUCCEED Project'

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

def get_cloudcare_app(module_id):
    from corehq.apps.cloudcare import api

    def get_latest_build(domain, app_id):
        build = ApplicationBase.view('app_manager/saved_app',
                                     startkey=[domain, app_id, {}],
                                     endkey=[domain, app_id],
                                     descending=True,
                                     limit=1).one()
        return build._doc if build else None

    apps = api.get_cloudcare_apps(SUCCEED_DOMAIN)
    filtered_app = filter(lambda x: x['name'] == SUCCEED_CLOUD_APPNAME, apps)
    app = api.look_up_app_json(SUCCEED_DOMAIN, filtered_app[0]['_id'])
    app_id = app['_id']
    module = app['modules'][module_id]
    forms = module['forms']
    ret = dict((f['xmlns'], ix) for (ix, f) in enumerate(forms))
    ret['domain'] = SUCCEED_DOMAIN
    latest_build = get_latest_build(SUCCEED_DOMAIN, app_id)
    if latest_build is not None:
        latest_build_id = latest_build['_id']
        ret['build_id'] = latest_build_id
    return ret


def _is_succeed_admin(user):
    return True if user.get_role()['name'] == CONFIG['succeed_admin'] else False


def _is_pm_or_pi(user):
    return True if 'role' in user.user_date and user.user_data['role'] in [CONFIG['pm_role'], CONFIG['pi_role']] else False


