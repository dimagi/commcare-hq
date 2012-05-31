from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.app_manager.views',
    url(r'^$', 'download_index', {}, 'download_index'),
    url(r'^suite.xml$', 'download_suite', {}, 'download_suite'),
    url(r'^profile.xml$', 'download_profile', {}, 'download_profile'),
    url(r'^profile.ccpr$', 'download_odk_profile', {}, 'download_odk_profile'),
    url(r'^(?P<lang>[\w-]+)/app_strings.txt$', 'download_app_strings', {}, 'download_app_strings'),

    url(r'^user_registration.xml$', 'download_user_registration', {}, 'download_user_registration'),
    url(r'^multimedia/commcare.zip$', 'download_multimedia_zip', {}, 'download_multimedia_zip'),
    url(r'^modules-(?P<module_id>\d+)/forms-(?P<form_id>\d+).xml$', 'download_xform', {}, 'download_xform'),
    url(r'^CommCare.jad$', 'download_jad', {}, 'download_jad'),
    url(r'^CommCare_raw.jar$', 'download_raw_jar', {}, 'download_raw_jar'),
    url(r'^CommCare.jar$', 'download_jar', {}, 'download_jar'),
)