# test data for corehq.apps.reports.tests.test_filters.TestEMWFilterOutput
dummy_user_list = [
    {
        'domain': 'emwf-filter-output-test',
        'username': 'active-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'activeworker@commcarehq.com',
        'uuid': 'active1',
        'is_active': True,
        'doc_type': 'CommcareUser',
        'user_domain_memberships': [
            {
                'domain': 'emwf-filter-output-test',
                'is_active': True,
            }
        ]
    },
    {
        'domain': 'emwf-filter-output-test',
        'username': 'active-worker-2',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'activeworker2@commcarehq.com',
        'uuid': 'active2',
        'is_active': True,
        'doc_type': 'CommcareUser',
        'user_domain_memberships': [
            {
                'domain': 'emwf-filter-output-test',
                'is_active': True,
            }
        ]
    },
    {
        'domain': 'emwf-filter-output-test',
        'username': 'deactivated-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'deactiveworker1@commcarehq.com',
        'uuid': 'deactive1',
        'is_active': False,
        'doc_type': 'CommcareUser',
        'user_domain_memberships': [
            {
                'domain': 'emwf-filter-output-test',
                'is_active': False,
            }
        ]
    },
    {
        'domain': 'emwf-filter-output-test',
        'username': 'deactivated-worker-2',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'deactiveworker2@commcarehq.com',
        'uuid': 'deactive2',
        'is_active': False,
        'doc_type': 'CommcareUser',
        'user_domain_memberships': [
            {
                'domain': 'emwf-filter-output-test',
                'is_active': False,
            }
        ]
    },
    {
        'domain': 'emwf-filter-output-test',
        'username': 'web-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'webworker@commcarehq.com',
        'uuid': 'web1',
        'is_active': True,
        "timezone": "UTC",
        'doc_type': 'WebUser',
        'user_domain_memberships': [
            {
                'domain': 'emwf-filter-output-test',
                'is_active': True,
            }
        ]
    },
]
