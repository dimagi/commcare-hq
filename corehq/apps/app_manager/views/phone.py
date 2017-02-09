from django.http import HttpResponse
from eulxml.xmlmap import XmlObject

from django.conf import settings

from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import check_lockout
from corehq.apps.users.models import CouchUser
from corehq.apps.app_manager.dbaccessors import get_built_app_ids, get_app
from corehq.apps.app_manager.suite_xml.xml_models import (
    StringField,
    IntegerField,
    NodeListField,
)


class App(XmlObject):
    ROOT_NAME = 'app'

    domain = StringField('@domain')
    name = StringField('@name')
    environment = StringField('@environment')
    version = IntegerField('@version')
    media_profile = StringField('@media-profile')
    profile = StringField('@profile')


class AppList(XmlObject):
    ROOT_NAME = 'apps'
    apps = NodeListField('app', App)


@check_lockout
@basicauth()
def list_apps(request):
    """Return a list of all apps available to the user

    Used by the phone for app installation
    """
    couch_user = CouchUser.from_django_user(request.user)
    return HttpResponse(
        get_app_list_xml(
            get_all_latest_builds_for_user(couch_user)
        ).serializeDocument(),
        content_type='application/xml',
    )


def get_all_latest_builds_for_user(user):
    app_ids = [
        (domain, app_id)
        for domain in user.domains
        for app_id in get_built_app_ids(domain)
    ]
    return [get_app(app_id[0], app_id[1], latest=True, target="release") for app_id in app_ids]


def get_app_list_xml(apps):
    app_xml = [
        App(
            domain=app.domain,
            name=app.name,
            version=app.version,
            media_profile=app.media_profile_url,
            profile=app.profile_url,
            environment=settings.SERVER_ENVIRONMENT,
        )
        for app in apps
    ]
    return AppList(apps=app_xml)
