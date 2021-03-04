from datetime import datetime

dummy_user_list = [
    {
        'domain': 'case-list-test',
        'username': 'active-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'activeworker@commcarehq.com',
        'uuid': 'active1',
        'is_active': True,
        'doc_type': 'CommcareUser'
    },
    {
        'domain': 'case-list-test',
        'username': 'active-worker-2',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'activeworker2@commcarehq.com',
        'uuid': 'active2',
        'is_active': True,
        'doc_type': 'CommcareUser'
    },
    {
        'domain': 'case-list-test',
        'username': 'deactivated-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'deactiveworker1@commcarehq.com',
        'uuid': 'deactive1',
        'is_active': False,
        'doc_type': 'CommcareUser'
    },
    {
        'domain': 'case-list-test',
        'username': 'web-worker-1',
        'password': 'Some secret Pass',
        'created_by': None,
        'created_via': None,
        'email': 'webworker@commcarehq.com',
        'uuid': 'web1',
        'is_active': True,
        "timezone": "UTC",
        'doc_type': 'WebUser'
    },
]


dummy_case_list = [
    {
        '_id': 'id-1',
        'domain': 'case-list-test',
        'name': 'Deactivated Owner case 1',
        'owner_id': 'deactive1',
        'user_id': 'deactivated-worker-1@commcarehq.org',
        'type': 'case',
        'opened_on': datetime(2021, 2, 24),
        'modified_on': None,
        'closed_on': None,
    },
    {
        '_id': 'id-2',
        'domain': 'case-list-test',
        'name': 'Active Owner case 1',
        'owner_id': 'active1',
        'user_id': 'active-worker-1@commcarehq.org',
        'type': 'case',
        'opened_on': datetime(2021, 2, 24),
        'modified_on': None,
        'closed_on': None,
    },
    {
        '_id': 'id-3',
        'domain': 'case-list-test',
        'name': 'Active Owner case 2',
        'owner_id': 'active1',
        'user_id': 'active-worker-1@commcarehq.org',
        'type': 'case',
        'opened_on': datetime(2021, 2, 24),
        'modified_on': None,
        'closed_on': None,
    },
    {
        '_id': 'id-4',
        'domain': 'case-list-test',
        'name': 'Web Owner case 1',
        'owner_id': 'web1',
        'user_id': 'active-worker-1@commcarehq.org',
        'type': 'case',
        'opened_on': datetime(2021, 2, 24),
        'modified_on': None,
        'closed_on': None,
    },
    {
        '_id': 'id-5',
        'domain': 'case-list-test',
        'name': 'Active Owner case 2',
        'owner_id': 'active2',
        'user_id': 'active-worker-2@commcarehq.org',
        'type': 'case',
        'opened_on': datetime(2021, 2, 24),
        'modified_on': None,
        'closed_on': None,
    },
]
