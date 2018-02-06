from __future__ import absolute_import
from corehq.apps.app_manager.dbaccessors import get_latest_released_app_version, get_app, get_latest_released_app
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.remote_accessors import get_released_app_version, get_released_app


def get_master_app_version(domain_link, app_id):
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
        master_app = get_app(master_domain, app_id)
        if linked_domain not in master_app.linked_whitelist:
            raise ActionNotPermitted()
        return get_latest_released_app(master_domain, app_id)
