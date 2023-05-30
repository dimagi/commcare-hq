import copy
import json
from datetime import datetime, timedelta, date
import pytz
from urllib.parse import urlencode

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

        self.assertEqual(len(result_objects), len(self.domain1_audits.expected_response_objects), result_objects)
        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], self.domain1_audits.expected_response_objects[i])

    def test_request_with_limit_param(self):
        limit = 1
        params = {'limit': limit}
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']

        self.assertEqual(len(result_objects), limit)
        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], self.domain1_audits.expected_response_objects[i])

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

        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], expected_result_objects[i])

    def test_request_with_user_param(self):
        users_filter = [self.username1]

        params = {'users': users_filter}
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        result_objects = json.loads(response.content)['objects']
        expected_result_objects = [
            d for d in self.domain1_audits.expected_response_objects
            if d['user'] in users_filter
        ]

        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], expected_result_objects[i])

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

        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], expected_result_objects[i])

    def test_request_with_cursor_param(self):
        params = {
            'cursor_user': self.username1,
            'cursor_local_date': date(2023, 5, 1).isoformat()
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
            {
                'user': self.username1,
                'user_id': self.user1._id,
                'local_date': date(2023, 5, 2).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC')).isoformat()
            },
            {
                'user': self.username2,
                'user_id': self.user2._id,
                'local_date': date(2023, 5, 2).isoformat(),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone('UTC')).isoformat(),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone('UTC')).isoformat()
            }
        ]

        for i in range(len(result_objects)):
            self.assertDictEqual(result_objects[i], expected_result_objects[i])

    def test_response_provides_next(self):
        params = {
            'limit': 1,
            'cursor_user': self.username1,
            'cursor_local_date': date(2023, 5, 1).isoformat()
        }
        list_endpoint = f'{self.list_endpoint}?{urlencode(params)}'
        response = self._assert_auth_get_resource(list_endpoint)
        self.assertEqual(response.status_code, 200)

        response_next_url = json.loads(response.content)['meta']['next']

        expected_next_params = {
            'limit': 1,
            'cursor_user': self.username2,
            'cursor_local_date': date(2023, 5, 1).isoformat()
        }
        expected_next_url = f'{self.list_endpoint}?{urlencode(expected_next_params)}'

        self.assertEqual(expected_next_url, response_next_url)

    def test_query_includes_users_in_only_specified_domain(self):
        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain1_audits.users)

        results = self.resource.cursor_query(self.domain2_audits.domain, self.domain2_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain2_audits.users)

    def test_query_first_last_action_time_for_each_user(self):
        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        self.assertListEqual(results, self.domain1_audits.expected_query_result)

    def test_query_ordered_by_local_date_and_user(self):
        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        filtered_results = [(result['local_date'], result['user']) for result in results]

        self.assertListEqual(filtered_results, sorted(filtered_results))

    def test_query_unique_local_date_and_user_pairs(self):
        #Query results should not have two entries with the same local date and user

        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
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
        params = {'users': [self.username1]}

        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result
            if item['user'] in params['users']
        ]

        self.assertListEqual(expected_results, results)

    def test_query_filter_by_local_date(self):
        date1 = date(2023, 5, 1)
        date2 = date(2023, 5, 2)
        params = {
            'local_date.gte': date(2023, 5, 1).isoformat(),
            'local_date.lt': date(2023, 5, 2).isoformat()
        }

        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params
        )
        expected_results = [
            item for item in self.domain1_audits.expected_query_result if
            (item['local_date'] >= date1 and item['local_date'] < date2)
        ]

        self.assertListEqual(expected_results, results)

    def test_query_cursor_pagination_returns_items_after_cursor(self):
        params = {
            'cursor_local_date': date(2023, 5, 1),
            'cursor_user': self.username1
        }

        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone, params)
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
        params = {
            'cursor_local_date': date(2023, 5, 1),
            'cursor_user': self.username1
        }

        params['limit'] = 2
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        self.assertEqual(len(results), params['limit'])

        params['limit'] = 3
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        self.assertEqual(len(results), params['limit'])

    def _daterange(start_datetime, end_datetime):
        for n in range(int((end_datetime - start_datetime).total_seconds() // 3600) + 1):
            yield start_datetime + timedelta(hours=n)
