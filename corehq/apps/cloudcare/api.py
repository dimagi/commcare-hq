from __future__ import absolute_import
from __future__ import unicode_literals

from couchdbkit.exceptions import ResourceNotFound
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.cloudcare.exceptions import RemoteAppError


def get_app_json(app):
    if not app:
        return None
    app_json = app.to_json()
    app_json['post_url'] = app.post_url
    return app_json


def look_up_app_json(domain, app_id):
    app = get_app(domain, app_id)
    if app.is_remote_app():
        raise RemoteAppError()
    assert(app.domain == domain)
    return get_app_json(app)


def get_cloudcare_app(domain, app_name):
    apps = get_cloudcare_apps(domain)
    app = [x for x in apps if x['name'] == app_name]
    if app:
        return look_up_app_json(domain, app[0]['_id'])
    else:
        raise ResourceNotFound(_("Not found application by name: %s") % app_name)
