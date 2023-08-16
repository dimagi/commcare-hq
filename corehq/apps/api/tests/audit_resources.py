import copy
from base64 import b64encode
import json
from datetime import datetime, timedelta, date
import pytz
from urllib.parse import urlencode
from functools import partial

from corehq.apps.api.resources import v0_5
from corehq.apps.users.models import WebUser
from corehq.apps.auditcare.models import NavigationEventAudit
from .utils import APIResourceTest
from corehq.util.test_utils import flag_enabled


class DomainNavigationEventAudits:
    def __init__(self, domain: str, project_timezone: pytz.tzinfo.DstTzInfo):
        self.domain = domain
        self.timezone = project_timezone
        self.users = set()

    def set_expected_resource_objects(self, expected_response: list[dict]):
        self.expected_response_objects = copy.deepcopy(expected_response)
        for obj in self.expected_response_objects:
            obj.update(
                local_date=obj['local_date'].isoformat(),
                UTC_start_time=obj['UTC_start_time'].isoformat(),
                UTC_end_time=obj['UTC_end_time'].isoformat()
            )

        self.expected_query_result = [{k: v for k, v in d.items() if k != 'user_id'} for d in expected_response]

    def create_event(self, user, event_date):
        self.users.add(user)
        NavigationEventAudit.objects.create(domain=self.domain, user=user, event_date=event_date)


@flag_enabled('ACTION_TIMES_API')
class TestNavigationEventAuditResource(APIResourceTest):
    resource = v0_5.NavigationEventAuditResource
    default_limit = resource._meta.limit
    max_limit = resource._meta.max_limit
    base_params = partial(v0_5.NavigationEventAuditResourceParams,
                          default_limit=default_limit, max_limit=max_limit)
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain.default_timezone = 'America/Los_Angeles'
        cls.domain.save()

        cls.domain1_audits = DomainNavigationEventAudits(cls.domain.name,
                                                        pytz.timezone(cls.domain.default_timezone))
        cls.domain2_audits = DomainNavigationEventAudits('domain2', pytz.timezone('America/Los_Angeles'))

        cls.username1 = 'andy@example.com'
        cls.username2 = 'bob@example.com'
        cls.username3 = 'chloe@example.com'

        cls.user1 = WebUser.create(cls.domain.name, cls.username1, '***', None, None)
        cls.user2 = WebUser.create(cls.domain.name, cls.username2, '***', None, None)

        cls.user1.save()
        cls.user2.save()

        for single_datetime in cls._daterange(datetime(2023, 5, 2, 0), datetime(2023, 5, 2, 23)):
            cls.domain1_audits.create_event(cls.username1, single_datetime)
            cls.domain1_audits.create_event(cls.username2, single_datetime)
            cls.domain1_audits.create_event(None, single_datetime)

        for single_datetime in cls._daterange(datetime(2023, 6, 1, 0), datetime(2023, 6, 1, 23)):
            cls.domain2_audits.create_event(cls.username3, single_datetime)

        cls.domain1_audits.set_expected_resource_objects([
            {
                'user': cls.username1,
                'user_id': cls.user1._id,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone('UTC'))
            },
            {
                'user': cls.username2,
                'user_id': cls.user2._id,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone('UTC'))
            },
            {
                'user': cls.username1,
                'user_id': cls.user1._id,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC'))
            },
            {
                'user': cls.username2,
                'user_id': cls.user2._id,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC'))
            }
        ])

    def test_request(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        self.assertEqual(result_objects, self.domain1_audits.expected_response_objects)

    def test_request_with_limit_param(self):
        limit = 1
        params = {'limit': limit}
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']

        self.assertEqual(len(result_objects), limit)
        self.assertEqual(result_objects, self.domain1_audits.expected_response_objects[:limit])

    def test_request_with_timezone_param(self):
        timezone = 'US/Eastern'

        params = {'local_timezone': timezone}
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            {
                'user': self.username1,
                'user_id': self.user1._id,
                'local_date': date(2023, 5, 1).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 3, tzinfo=pytz.timezone('UTC')).isoformat()
            },
            {
                'user': self.username2,
                'user_id': self.user2._id,
                'local_date': date(2023, 5, 1).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 3, tzinfo=pytz.timezone('UTC')).isoformat()
            },
            {
                'user': self.username1,
                'user_id': self.user1._id,
                'local_date': date(2023, 5, 2).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 4, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC')).isoformat()
            },
            {
                'user': self.username2,
                'user_id': self.user2._id,
                'local_date': date(2023, 5, 2).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 4, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC')).isoformat()
            }
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_request_with_user_param(self):
        users_filter = [self.username1]

        params = {'users': users_filter}
        list_endpoint = f'{self.list_endpoint}?{urlencode(params, True)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            d for d in self.domain1_audits.expected_response_objects
            if d['user'] in users_filter
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_request_with_date_param(self):
        date1 = date(2023, 5, 1).isoformat()
        date2 = date(2023, 5, 2).isoformat()

        params = {
            'local_date.gte': date1,
            'local_date.lt': date2,
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            item for item in self.domain1_audits.expected_response_objects if
            (item['local_date'] >= date1 and item['local_date'] < date2)
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_request_with_UTC_start_time_start_param(self):
        start_datetime = datetime(2023, 5, 2, 1, tzinfo=pytz.timezone('UTC')).isoformat()

        params = {
            'UTC_start_time_start': start_datetime,
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            item for item in self.domain1_audits.expected_response_objects if
            (item['UTC_start_time'] >= start_datetime)
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_request_with_UTC_start_time_end_param(self):
        end_datetime = datetime(2023, 5, 2, 1, tzinfo=pytz.timezone('UTC')).isoformat()

        params = {
            'UTC_start_time_end': end_datetime,
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            item for item in self.domain1_audits.expected_response_objects if
            (item['UTC_start_time'] <= end_datetime)
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_request_with_cursor_param(self):
        cursor = {
            'cursor_user': self.username1,
            'cursor_local_date': date(2023, 5, 1).isoformat(),
            'local_date.lt': date(2023, 5, 2).isoformat()
        }
        encoded_cursor = b64encode(urlencode(cursor).encode('utf-8'))
        params = {
            'cursor': encoded_cursor,
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            {
                'user': self.username2,
                'user_id': self.user2._id,
                'local_date': date(2023, 5, 1).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone('UTC')).isoformat()
            },
        ]

        self.assertEqual(result_objects, expected_result_objects)

    def test_response_provides_next(self):
        local_date_filter = date(2023, 5, 2).isoformat()

        # Tests initial request without a cursor
        params = {
            'limit': 1,
            'local_date.lte': local_date_filter
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_next_url = json.loads(response.content)['meta']['next']

        expected_page_zero_cursor = {
            'limit': 1,
            'local_date.lte': local_date_filter,
            'cursor_local_date': date(2023, 5, 1).isoformat(),
            'cursor_user': self.username1
        }
        encoded_expected_cursor = b64encode(urlencode(expected_page_zero_cursor).encode('utf-8'))
        expected_next_params = {
            'cursor': encoded_expected_cursor,
        }
        expected_next_url = f'?{urlencode(expected_next_params)}'
        self.assertEqual(expected_next_url, response_next_url)

        # Tests follow-up request using previously returned cursor
        encoded_cursor = b64encode(urlencode(expected_page_zero_cursor).encode('utf-8'))
        params = {
            'limit': 1,
            'cursor': encoded_cursor,
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_next_url = json.loads(response.content)['meta']['next']

        expected_page_one_cursor = {
            'limit': 1,
            'local_date.lte': local_date_filter,
            'cursor_local_date': date(2023, 5, 1).isoformat(),
            'cursor_user': self.username2
        }
        encoded_expected_cursor = b64encode(urlencode(expected_page_one_cursor).encode('utf-8'))
        expected_next_params = {
            'cursor': encoded_expected_cursor,
        }
        expected_next_url = f'?{urlencode(expected_next_params)}'
        self.assertEqual(expected_next_url, response_next_url)

    def test_response_provides_total_count(self):
        limit = 1
        params = {'limit': limit}

        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_total_count = json.loads(response.content)['meta']['total_count']
        self.assertEqual(len(self.domain1_audits.expected_response_objects),
                        response_total_count)

        params['local_timezone'] = 'UTC'
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)
        response_total_count = json.loads(response.content)['meta']['total_count']
        self.assertEqual(2, response_total_count)

    def test_query_includes_users_in_only_specified_domain(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(self.domain1_audits.domain, params)
        for result in results:
            self.assertTrue(result['user'] in self.domain1_audits.users)

        params.local_timezone = self.domain2_audits.timezone
        results = self.resource.cursor_query(self.domain2_audits.domain, params)
        for result in results:
            self.assertTrue(result['user'] in self.domain2_audits.users)

    def test_query_first_last_action_time_for_each_user(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(self.domain1_audits.domain, params)
        self.assertListEqual(results, self.domain1_audits.expected_query_result)

    def test_query_ordered_by_local_date_and_user(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(self.domain1_audits.domain, params)
        filtered_results = [(result['local_date'], result['user']) for result in results]

        self.assertListEqual(filtered_results, sorted(filtered_results))

    def test_query_unique_local_date_and_user_pairs(self):
        #Query results should not have two entries with the same local date and user

        params = self.base_params(domain=self.domain1_audits.domain)
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(self.domain1_audits.domain, params)
        seen_user_local_dates = {}
        for result in results:
            user = result['user']
            local_date = result['local_date']

            if user in seen_user_local_dates:
                self.assertNotIn(local_date, seen_user_local_dates[user])
            else:
                seen_user_local_dates[user] = set()
            seen_user_local_dates[user].add(local_date)

    def test_query_filter_by_user(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.users = [self.username1]
        params.local_timezone = self.domain1_audits.timezone

        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params,
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result
            if item['user'] in params.users
        ]

        self.assertListEqual(expected_results, results)

    def test_query_filter_by_local_date(self):
        date1 = date(2023, 5, 1)
        date2 = date(2023, 5, 2)

        params = self.base_params(domain=self.domain1_audits.domain)
        local_date_params = {
            'gte': date(2023, 5, 1).isoformat(),
            'lt': date(2023, 5, 2).isoformat()
        }

        params.local_date = local_date_params
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result if
            (item['local_date'] >= date1 and item['local_date'] < date2)
        ]

        self.assertListEqual(expected_results, results)

    def test_query_filter_by_UTC_start_time_start(self):
        start_datetime = datetime(2023, 5, 2, 1, tzinfo=pytz.timezone('UTC'))
        params = self.base_params(domain=self.domain1_audits.domain)
        params.UTC_start_time_start = start_datetime
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result if
            (item['UTC_start_time'] >= start_datetime)
        ]

        self.assertListEqual(expected_results, results)

    def test_query_filter_by_UTC_start_time_end(self):
        end_datetime = datetime(2023, 5, 2, 6, tzinfo=pytz.timezone('UTC'))
        params = self.base_params(domain=self.domain1_audits.domain)
        params.UTC_start_time_end = end_datetime
        params.local_timezone = self.domain1_audits.timezone
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result if
            (item['UTC_end_time'] <= end_datetime)
        ]

        self.assertListEqual(expected_results, results)

    def test_query_cursor_pagination_returns_items_after_cursor(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.cursor_local_date = date(2023, 5, 1)
        params.cursor_user = self.username1
        params.local_timezone = self.domain1_audits.timezone

        results = self.resource.cursor_query(self.domain1_audits.domain, params)
        expected_results = [
            {
                'user': self.username2,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone('UTC'))
            },
            {
                'user': self.username1,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC'))
            },
            {
                'user': self.username2,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC'))
            }
        ]

        self.assertListEqual(expected_results, results)

    def test_query_cursor_pagination_page_size(self):
        params = self.base_params(domain=self.domain1_audits.domain)
        params.cursor_local_date = date(2023, 5, 1)
        params.cursor_user = self.username1
        params.local_timezone = self.domain1_audits.timezone

        params.limit = 2
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params,
        )
        self.assertEqual(len(results), params.limit)

        params.limit = 3
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            params=params,
        )
        self.assertEqual(len(results), params.limit)

    def _daterange(start_datetime, end_datetime):
        for n in range(int((end_datetime - start_datetime).total_seconds() // 3600) + 1):
            yield start_datetime + timedelta(hours=n)
