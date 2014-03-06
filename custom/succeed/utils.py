from corehq.apps.app_manager.models import ApplicationBase

SUCCEED_DOMAIN = 'succeed'
SUCCEED_CLOUD_APPNAME = 'SUCCEED Project'

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
