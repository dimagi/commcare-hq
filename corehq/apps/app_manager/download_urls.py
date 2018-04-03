from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.app_manager.views import (
    download_index, download_suite, download_media_suite, download_profile,
    download_media_profile, download_odk_profile, download_odk_media_profile,
    download_app_strings, download_xform, download_jad, download_raw_jar,
    download_jar, download_practice_user_restore
)

urlpatterns = [
    url(r'^$', download_index, {}, 'download_index'),
    url(r'^suite.xml$', download_suite, {}, 'download_suite'),
    url(r'^media_suite.xml$', download_media_suite, {}, 'download_media_suite'),
    url(r'^profile.xml$', download_profile, {}, 'download_profile'),
    url(r'^media_profile.xml$', download_media_profile, {}, 'download_media_profile'),
    url(r'^profile.ccpr$', download_odk_profile, {}, 'download_odk_profile'),
    url(r'^media_profile.ccpr$', download_odk_media_profile, {}, 'download_odk_media_profile'),
    url(r'^practice_user_restore.xml$', download_practice_user_restore, {}, 'download_practice_user_restore'),
    url(r'^(?P<lang>[\w-]+)/app_strings.txt$', download_app_strings, {}, 'download_app_strings'),
    url(r'^modules-(?P<module_id>\d+)/forms-(?P<form_id>\d+).xml$', download_xform, {}, 'download_xform'),
    url(r'^CommCare.jad$', download_jad, {}, 'download_jad'),
    url(r'^CommCare_raw.jar$', download_raw_jar, {}, 'download_raw_jar'),
    url(r'^CommCare.jar$', download_jar, {}, 'download_jar'),
]
