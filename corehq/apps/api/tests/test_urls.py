from corehq.apps.api import urls as api_urls

# Snapshot of corehq.apps.api.urls.urlpatterns, in resolution order.
# Django matches URLs in order, so both membership and order matter.
EXPECTED_DOMAIN_PATTERNS = [
    '(?P<api_version>v0.5)/odata/cases/',
    '(?P<api_version>v0.5)/odata/forms/',
    'odata/cases/(?P<api_version>v1)/',
    'odata/forms/(?P<api_version>v1)/',
    '(?P<api_version>v0.5)/messaging-event/$',
    '(?P<api_version>v0.5)/messaging-event/(?P<event_id>\\d+)/$',
    'messaging-event/(?P<api_version>v1)/$',
    'messaging-event/(?P<api_version>v1)/(?P<event_id>\\d+)/$',
    'v0\\.6/case/bulk-fetch/$',
    'v0.6/case/?$',
    'v0\\.6/case/(?P<case_id>[\\w\\-,]+)/?$',
    'v0.6/case/ext/<path:external_id>/',
    'case/v2/bulk-fetch/$',
    'case/v2/?$',
    'case/v2/(?P<case_id>[\\w\\-,]+)/?$',
    'case/v2/ext/<path:external_id>/',
    '',
    '^case/attachment/(?P<case_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^case_attachment/v1/(?P<case_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^form/attachment/(?P<instance_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    '^form_attachment/v1/(?P<instance_id>[\\w\\-:]+)/(?P<attachment_id>.*)$',
    'case/custom/<slug:api_id>/',
    '(?P<api_version>v0.5)/ucr/',
    'ucr/(?P<api_version>v1)/',
    '^(?P<resource_name>application)/(?P<api_name>v1)/',
    '^(?P<resource_name>case)/(?P<api_name>v1)/',
    '^(?P<resource_name>form)/(?P<api_name>v1)/',
    '^(?P<resource_name>sso)/(?P<api_name>v1)/',
    '^(?P<resource_name>user)/(?P<api_name>v1)/',
    '^(?P<resource_name>web-user)/(?P<api_name>v1)/',
    '^(?P<resource_name>group)/(?P<api_name>v1)/',
    '^(?P<resource_name>bulk-user)/(?P<api_name>v1)/',
    '^(?P<resource_name>fixture_internal)/(?P<api_name>v1)/',
    '^(?P<resource_name>fixture)/(?P<api_name>v1)/',
    '^(?P<resource_name>device-log)/(?P<api_name>v1)/',
    '^(?P<resource_name>project_space_metadata)/(?P<api_name>v1)/',
    '^(?P<resource_name>location)/(?P<api_name>v1)/',
    '^(?P<resource_name>location)/(?P<api_name>v2)/',
    '^(?P<resource_name>location_type)/(?P<api_name>v1)/',
    '^(?P<resource_name>simplereportconfiguration)/(?P<api_name>v1)/',
    '^(?P<resource_name>configurablereportdata)/(?P<api_name>v1)/',
    '^(?P<resource_name>ucr_data_source)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_forms)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_cases)/(?P<api_name>v1)/',
    '^(?P<resource_name>domain_usernames)/(?P<api_name>v1)/',
    '^(?P<resource_name>location_internal)/(?P<api_name>v1)/',
    '^(?P<resource_name>odata/cases)/(?P<api_name>v1)/',
    '^(?P<resource_name>odata/forms)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table_item)/(?P<api_name>v1)/',
    '^(?P<resource_name>lookup_table_item)/(?P<api_name>v2)/',
    '^(?P<resource_name>action_times)/(?P<api_name>v1)/',
    '^(?P<resource_name>analytics-roles)/(?P<api_name>v1)/',
    '^(?P<resource_name>invitation)/(?P<api_name>v1)/',
    '^(?P<resource_name>det_export_instance)/(?P<api_name>v1)/',
]

EXPECTED_USER_PATTERNS = [
    '',
    '^(?P<resource_name>identity)/(?P<api_name>v1)/',
    '^(?P<resource_name>user_domains)/(?P<api_name>v1)/',
]


def test_domain_url_patterns_and_order_unchanged():
    actual = [str(p.pattern) for p in api_urls.urlpatterns]
    assert actual == EXPECTED_DOMAIN_PATTERNS


def test_user_url_patterns_and_order_unchanged():
    actual = [str(p.pattern) for p in api_urls.user_urlpatterns]
    assert actual == EXPECTED_USER_PATTERNS
