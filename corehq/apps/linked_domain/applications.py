from __future__ import absolute_import

from __future__ import unicode_literals
from corehq.apps.app_manager.dbaccessors import get_latest_released_app_version, get_app, get_latest_released_app
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.remote_accessors import get_released_app_version, get_released_app


def get_master_app_version(domain_link, app_id):    # TODO: rename to get_upstream_version? delete?
    if domain_link.is_remote:
        return get_released_app_version(domain_link.master_domain, app_id, domain_link.remote_details)
    else:
        return get_latest_released_app_version(domain_link.master_domain, app_id)


def get_latest_master_app_release(domain_link, app_id):
    master_domain = domain_link.master_domain
    linked_domain = domain_link.linked_domain
    if domain_link.is_remote:
        return get_released_app(master_domain, app_id, linked_domain, domain_link.remote_details)
    else:
        return get_latest_released_app(master_domain, app_id)


def create_linked_app(master_domain, master_id, target_domain, target_name, remote_details=None):
    from corehq.apps.app_manager.models import LinkedApplication
    linked_app = LinkedApplication(
        name=target_name,
        domain=target_domain,
    )
    return link_app(linked_app, master_domain, master_id, remote_details)


def link_app(linked_app, master_domain, master_id, remote_details=None):
    DomainLink.link_domains(linked_app.domain, master_domain, remote_details)

    linked_app.master = master_id
    linked_app.doc_type = 'LinkedApplication'
    linked_app.save()
    return linked_app
