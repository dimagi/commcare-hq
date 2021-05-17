from collections import defaultdict

from django.conf import settings

from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_brief_app_docs_in_domain,
    get_build_doc_by_version,
    get_latest_released_app,
    get_latest_released_app_versions_by_app_id,
    wrap_app, get_app, get_apps_in_domain,
)
from corehq.apps.app_manager.exceptions import AppLinkError
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.exceptions import MultipleDownstreamAppsError, RemoteRequestError
from corehq.apps.linked_domain.remote_accessors import (
    get_app_by_version,
    get_brief_apps,
    get_latest_released_versions_by_app_id,
    get_released_app,
)
from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app
from corehq.util.quickcache import quickcache


def get_master_app_briefs(domain_link, family_id):
    if domain_link.is_remote:
        apps = get_brief_apps(domain_link)
    else:
        apps = get_brief_apps_in_domain(domain_link.master_domain, include_remote=False)

    # Ignore deleted, linked and remote apps
    return [app for app in apps if family_id in [app._id, app.family_id] and app.doc_type == 'Application']


def get_master_app_by_version(domain_link, upstream_app_id, upstream_version):
    if domain_link.is_remote:
        app = get_app_by_version(domain_link, upstream_app_id, upstream_version)
    else:
        app = get_build_doc_by_version(domain_link.master_domain, upstream_app_id, upstream_version)

    if app:
        return wrap_app(app)


def get_downstream_app_id(downstream_domain, upstream_app_id):
    downstream_ids = _get_downstream_app_id_map(downstream_domain)[upstream_app_id]
    if not downstream_ids:
        return None
    if len(downstream_ids) > 1:
        raise MultipleDownstreamAppsError
    return downstream_ids[0]


def get_upstream_app_ids(downstream_domain):
    return list(_get_downstream_app_id_map(downstream_domain))


@quickcache(vary_on=['downstream_domain'], skip_arg=lambda _: settings.UNIT_TESTING, timeout=5 * 60)
def _get_downstream_app_id_map(downstream_domain):
    downstream_app_ids = defaultdict(list)
    for doc in get_brief_app_docs_in_domain(downstream_domain):
        if doc.get("family_id"):
            downstream_app_ids[doc["family_id"]].append(doc["_id"])
    return downstream_app_ids


def get_latest_master_app_release(domain_link, app_id):
    master_domain = domain_link.master_domain
    linked_domain = domain_link.linked_domain
    if domain_link.is_remote:
        return get_released_app(master_domain, app_id, linked_domain, domain_link.remote_details)
    else:
        return get_latest_released_app(master_domain, app_id)


def get_latest_master_releases_versions(domain_link):
    if domain_link.is_remote:
        return get_latest_released_versions_by_app_id(domain_link)
    else:
        return get_latest_released_app_versions_by_app_id(domain_link.master_domain)


def get_linked_apps_for_domain(domain):
    linked_apps = []
    apps = get_apps_in_domain(domain, include_remote=False)
    for app in apps:
        if is_linked_app(app):
            linked_apps.append(app)

    return linked_apps


def _create_linked_app(domain, app_name, upstream_app_id):
    from corehq.apps.app_manager.models import LinkedApplication
    linked_app = LinkedApplication(
        domain=domain,
        name=app_name,
        upstream_app_id=upstream_app_id,
    )
    linked_app.save()
    return linked_app


def create_linked_app(upstream_domain, upstream_id, downstream_domain, app_name=None, remote_details=None):
    DomainLink.link_domains(downstream_domain, upstream_domain, remote_details)
    if not app_name:
        original_app = get_app(upstream_domain, upstream_id)
        app_name = original_app.name

    linked_app = _create_linked_app(downstream_domain, app_name, upstream_id)
    return handle_special_cases_for_linked_app(linked_app)


def _pull_multimedia_if_remote(linked_app):
    if linked_app.master_is_remote:
        try:
            pull_missing_multimedia_for_app(linked_app)
        except RemoteRequestError:
            raise AppLinkError('Error fetching multimedia from remote server. Please try again later.')


def handle_special_cases_for_linked_app(linked_app):
    """
    These are misc. methods to update a recently linked app
    Clearing the downstream app id map is related to multi-master apps and may be removed soon
    """
    _pull_multimedia_if_remote(linked_app)
    _get_downstream_app_id_map.clear(linked_app.domain)
    return linked_app


def unlink_apps_in_domain(domain):
    linked_apps = get_linked_apps_for_domain(domain)
    unlinked_apps = []
    for app in linked_apps:
        unlinked_app = unlink_app(app)
        unlinked_apps.append(unlinked_app)

    return unlinked_apps


def unlink_app(linked_app):
    if not is_linked_app(linked_app):
        return None

    converted_app = linked_app.convert_to_application()
    converted_app.save()

    return converted_app
