from __future__ import absolute_import
from corehq.apps.app_manager.dbaccessors import get_latest_released_app_version, get_app, get_latest_released_app
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.linked_domain.remote_accessors import get_released_app_version, get_released_app


def get_master_app_version(master_domain, app_id, remote_details=None):
    if remote_details:
        return get_released_app_version(master_domain, app_id, remote_details)
    else:
        return get_latest_released_app_version(master_domain, app_id)


def get_latest_master_app_release(master_domain, app_id, linked_domain, remote_details=None):
    if remote_details:
        return get_released_app(master_domain, app_id, linked_domain, remote_details)
    else:
        master_app = get_app(master_domain, app_id)
        if linked_domain not in master_app.linked_whitelist:
            raise ActionNotPermitted()
        return get_latest_released_app(master_domain, app_id)
