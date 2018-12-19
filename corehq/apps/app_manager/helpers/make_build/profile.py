# coding=utf-8
from __future__ import absolute_import, unicode_literals

from collections import defaultdict
from django.template.loader import render_to_string

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager import commcare_settings
from corehq.apps.app_manager.const import *
from corehq.apps.users.util import cc_user_domain


ANDROID_LOGO_PROPERTY_MAPPING = {
    'hq_logo_android_home': 'brand-banner-home',
    'hq_logo_android_login': 'brand-banner-login',
}


class ProfileGenerator(object):
    def __init__(self, app):
        self.app = app
        self.domain = app.domain

    def create(self, is_odk=False, with_media=False, build_profile_id=None, target_commcare_flavor=None):
        self__profile = self.app.profile
        app_profile = defaultdict(dict)

        for setting in commcare_settings.get_custom_commcare_settings():
            setting_type = setting['type']
            setting_id = setting['id']

            if setting_type not in ('properties', 'features'):
                setting_value = None
            elif setting_id not in self__profile.get(setting_type, {}):
                if 'commcare_default' in setting and setting['commcare_default'] != setting['default']:
                    setting_value = setting['default']
                else:
                    setting_value = None
            else:
                setting_value = self__profile[setting_type][setting_id]
            if setting_value:
                app_profile[setting_type][setting_id] = {
                    'value': setting_value,
                    'force': setting.get('force', False)
                }
            # assert that it gets explicitly set once per loop
            del setting_value

        if self.app.case_sharing:
            app_profile['properties']['server-tether'] = {
                'force': True,
                'value': 'sync',
            }

        logo_refs = [logo_name for logo_name in self.app.logo_refs if logo_name in ANDROID_LOGO_PROPERTY_MAPPING]
        if logo_refs and domain_has_privilege(self.domain, privileges.COMMCARE_LOGO_UPLOADER):
            for logo_name in logo_refs:
                app_profile['properties'][ANDROID_LOGO_PROPERTY_MAPPING[logo_name]] = {
                    'value': self.app.logo_refs[logo_name]['path'],
                }

        if toggles.MOBILE_RECOVERY_MEASURES.enabled(self.domain):
            app_profile['properties']['recovery-measures-url'] = {
                'force': True,
                'value': self.app.recovery_measures_url,
            }

        if with_media:
            profile_url = self.app.media_profile_url if not is_odk else (self.app.odk_media_profile_url + '?latest=true')
        else:
            profile_url = self.app.profile_url if not is_odk else (self.app.odk_profile_url + '?latest=true')

        if toggles.CUSTOM_PROPERTIES.enabled(self.domain) and "custom_properties" in self__profile:
            app_profile['custom_properties'].update(self__profile['custom_properties'])

        apk_heartbeat_url = self.app.heartbeat_url
        locale = self.app.get_build_langs(build_profile_id)[0]
        target_package_id = {
            TARGET_COMMCARE: 'org.commcare.dalvik',
            TARGET_COMMCARE_LTS: 'org.commcare.lts',
        }.get(target_commcare_flavor)
        return render_to_string('app_manager/profile.xml', {
            'is_odk': is_odk,
            'app': self.app,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'uniqueid': self.app.master_id,
            'name': self.app.name,
            'descriptor': "Profile File",
            'build_profile_id': build_profile_id,
            'locale': locale,
            'apk_heartbeat_url': apk_heartbeat_url,
            'target_package_id': target_package_id,
        }).encode('utf-8')
