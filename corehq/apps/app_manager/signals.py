from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch.dispatcher import Signal

from corehq.apps.callcenter.app_parser import get_call_center_config_from_app
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.util import (
    get_latest_enabled_build_for_profile,
    get_latest_enabled_app_release,
)
from corehq.apps.app_manager.util import get_latest_enabled_versions_per_profile
from corehq import toggles
from dimagi.utils.logging import notify_exception

from corehq.apps.locations.models import SQLLocation


def create_app_structure_repeat_records(sender, application, **kwargs):
    from corehq.motech.repeaters.models import AppStructureRepeater
    domain = application.domain
    if domain:
        repeaters = AppStructureRepeater.by_domain(domain)
        for repeater in repeaters:
            repeater.register(application)


def update_callcenter_config(sender, application, **kwargs):
    if not application.copy_of:
        return

    try:
        domain_obj = Domain.get_by_name(application.domain)
        cc_config = domain_obj.call_center_config
        if not cc_config or not (cc_config.fixtures_are_active() and cc_config.config_is_valid()):
            return

        app_config = get_call_center_config_from_app(application)
        save = cc_config.update_from_app_config(app_config)
        if save:
            cc_config.save()
    except Exception:
        notify_exception(None, "Error updating CallCenter config for app build")


def expire_latest_enabled_build_profiles(sender, application, **kwargs):
    if application.copy_of and toggles.RELEASE_BUILDS_PER_PROFILE.enabled(application.domain):
        for build_profile_id in application.build_profiles:
            get_latest_enabled_build_for_profile.clear(application.domain, build_profile_id)
        get_latest_enabled_versions_per_profile.clear(application.copy_of)


def expire_get_latest_enabled_app_release(sender, latest_enabled_app_release, **kwargs):
    """
    expire cache for the location and its descendants for the app corresponding to this enabled app release
    why? : Latest enabled release for a location is dependent on restrictions added for
    itself and its ancestors. Hence we expire the cache for location and its descendants for which the
    latest enabled release would depend on this location
    """
    location = SQLLocation.active_objects.get(location_id=latest_enabled_app_release.location_id)
    location_and_descendats = location.get_descendants(include_self=True)
    for loc in location_and_descendats:
        get_latest_enabled_app_release.clear(latest_enabled_app_release.domain, loc.location_id,
                                             latest_enabled_app_release.app_id)


app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)
app_post_save.connect(update_callcenter_config)
app_post_save.connect(expire_latest_enabled_build_profiles)

app_post_release = Signal(providing_args=['application'])
latest_enabled_app_release_post_save = Signal(providing_args=['latest_enabled_app_release'])
latest_enabled_app_release_post_save.connect(expire_get_latest_enabled_app_release)
