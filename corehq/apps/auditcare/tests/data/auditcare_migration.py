from datetime import datetime
navigation_test_docs = [
    {
        'description': 'Test User',
        'extra': {},
        'status_code': 200,
        'user': 'user@test.org',
        'session_key': '14f8fb95aece47d8341dc561dfd108df',
        'ip_address': '0.0.0.0',
        'request_path': '/a/test-domain/reports/',
        'view_kwargs': {
            'domain': 'test-domain'
        },
        'doc_type': 'NavigationEventAudit',
        'headers': {
            'REQUEST_METHOD': 'GET',
            'SERVER_PORT': '443',
        },
        'base_type': 'AuditEvent',
        'user_agent': 'Mozilla/5.0 (Windows NT 5.1)',
        'event_date': '2021-06-01T00:13:01Z',
        'view': 'corehq.apps.reports.views.default'
    },
    {
        'description': 'Test User',
        'extra': {},
        'status_code': 200,
        'user': 'user@test.org',
        'session_key': '14f8fb95aece47d8341dc561dfd108df',
        'ip_address': '0.0.0.0',
        'request_path': '/a/test-domain/reports/',
        'view_kwargs': {
            'domain': 'test-domain'
        },
        'doc_type': 'NavigationEventAudit',
        'headers': {
            'REQUEST_METHOD': 'GET',
            'SERVER_PORT': '443',
        },
        'base_type': 'AuditEvent',
        'user_agent': 'Mozilla/5.0 (Windows NT 5.1)',
        'event_date': '2021-06-01T01:13:01Z',
        'view': 'corehq.apps.reports.views.default'
    },
    {
        'description': 'Test User',
        'extra': {},
        'status_code': 200,
        'user': 'user@test.org',
        'session_key': '14f8fb95aece47d8341dc561dfd108df',
        'ip_address': '0.0.0.0',
        'request_path': '/a/test-domain/reports/',
        'view_kwargs': {
            'domain': 'test-domain'
        },
        'doc_type': 'NavigationEventAudit',
        'headers': {
            'SERVER_NAME': 'www.commcarehq.org',
            'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.8',
            'REQUEST_METHOD': 'GET',
            'HTTP_ACCEPT_ENCODING': 'gzip,deflate,sdch'
        },
        'base_type': 'AuditEvent',
        'user_agent': 'Mozilla/5.0 (Windows NT 5.1)',
        'event_date': '2021-06-01T00:01:00Z',
        'view': 'corehq.apps.reports.views.default'
    }
]

audit_test_docs = [
    {
        'http_accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'doc_type': 'AccessAudit',
        'description': 'Login Success',
        'get_data': [],
        'access_type': 'login',
        'base_type': 'AuditEvent',
        'post_data': [],
        'user_agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64)',
        'failures_since_start': None,
        'event_date': '2021-06-15T04:23:32Z',
        'path_info': '/accounts/login/',
        'session_key': 'sess_key',
        'ip_address': '0.0.0.0',
        'user': 'login@test.org'
    },
    {
        'access_type': 'logout',
        'ip_address': '0.0.0.0',
        'session_key': 'sess_key',
        'user_agent': None,
        'get_data': [],
        'post_data': [],
        'http_accept': None,
        'path_info': None,
        'failures_since_start': None,
        'doc_type': 'AccessAudit',
        'user': 'logout@test.org',
        'base_type': 'AuditEvent',
        'event_date': '2021-06-24T00:00:00.15Z',
        'description': 'Logout test'
    }
]

failed_docs = [
    {
        'http_accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'doc_type': 'AccessAudit',
        'description': 'Login Success',
        'get_data': [],
        'access_type': 'login',
        'base_type': 'AuditEvent',
        'post_data': [],
        'user_agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64)',
        'failures_since_start': None,
        'event_date': '2021-05-15T04:23:32Z',
        'path_info': '/accounts/login/',
        'session_key': 'sess_key',
        'ip_address': '0.0.0.0',
        'user': 'failed@test.org',
    },
    {
        'description': 'Test User',
        'extra': {},
        'status_code': 200,
        'user': 'user@test.org',
        'session_key': '14f8fb95aece47d8341dc561dfd108df',
        'ip_address': '0.0.0.0',
        'request_path': '/a/test-domain/reports/',
        'view_kwargs': {
            'domain': 'test-domain'
        },
        'doc_type': 'NavigationEventAudit',
        'headers': {
            'SERVER_NAME': 'www.commcarehq.org',
            'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.8',
            'REQUEST_METHOD': 'GET',
            'HTTP_ACCEPT_ENCODING': 'gzip,deflate,sdch'
        },
        'base_type': 'AuditEvent',
        'user_agent': 'Mozilla/5.0 (Windows NT 5.1)',
        'event_date': '2021-05-01T00:01:00Z',
        'view': 'corehq.apps.reports.views.default'
    }
]
task_docs = [
    {
        'doc_type': 'NavigationEventAudit',
        'user': 'couch@test.com',
        'event_date': datetime(2021, 1, 1).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'description': 'User Name',
        'extra': {},
        'headers': {
            'REQUEST_METHOD': 'GET',
        },
        'ip_address': '10.1.2.3',
        'request_path': '/a/delmar/phone/restore/?version=2.0&since=...',
        'session_key': 'abc123',
        'status_code': 200,
        'view_kwargs': {'domain': 'delmar'},
        'view': 'corehq.apps.ota.views.restore',
    },
    {
        'doc_type': 'NavigationEventAudit',
        'user': 'couch@test.com',
        'event_date': datetime(2021, 2, 1, 2).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'description': 'User Name',
        'extra': {},
        'headers': {
            'REQUEST_METHOD': 'GET',
        },
        'ip_address': '10.1.2.3',
        'request_path': '/a/test-space/phone/restore/?version=2.0&since=...',
        'session_key': 'abc123',
        'status_code': 200,
        'view_kwargs': {'domain': 'test-space'},
        'view': 'corehq.apps.ota.views.restore',
    },
    {
        'doc_type': 'NavigationEventAudit',
        'user': 'couch@test.com',
        'event_date': datetime(2021, 2, 1, 2, 1).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'description': 'User Name',
        'extra': {},
        'headers': {
            'REQUEST_METHOD': 'GET',
        },
        'ip_address': '10.1.2.3',
        'request_path': '/a/random/phone/restore/?version=2.0&since=...',
        'session_key': 'abc123',
        'status_code': 200,
        'view_kwargs': {'domain': 'random'},
        'view': 'corehq.apps.ota.views.restore',
    },
    {
        'doc_type': "AccessAudit",
        'user': 'couch@test.com',
        'event_date': datetime(2021, 2, 1, 3).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'access_type': 'login',
        'description': 'Login Success',
        'failures_since_start': None,
        'get_data': [],
        'http_accept': 'text/html',
        'ip_address': '10.1.3.2',
        'path_info': '/a/delmar/login/',
        'post_data': [],
        'session_key': 'abc123',
        'user_agent': 'Mozilla/5.0',
    },
    {
        'doc_type': 'NavigationEventAudit',
        'user': 'couch@test.com',
        'event_date': datetime(2021, 2, 1, 5).strftime("%Y-%m-%dT%H:%M:%SZ"),
        'description': 'User Name',
        'extra': {},
        'headers': {
            'REQUEST_METHOD': 'GET',
        },
        'ip_address': '10.1.2.3',
        'request_path': '/a/sandwich/phone/restore/?version=2.0&since=...',
        'session_key': 'abc123',
        'status_code': 200,
        'view_kwargs': {'domain': 'sandwich'},
        'view': 'corehq.apps.ota.views.restore',
    }
]
