from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.cloudcare.api import get_app_json

def all_domain_apps_versions(apps, domain):
        all_app_versions = []
        for app in apps:
            builds = ApplicationBase.view('app_manager/saved_app',
                                         startkey=[domain, app["_id"], {}],
                                         endkey=[domain, app["_id"]],
                                         descending=True).all()
            for build in builds:
                all_app_versions.append(get_app_json(build) if build else None)

        return all_app_versions