import json
import urllib.parse
from datetime import datetime, timedelta
from operator import attrgetter
from urllib.parse import urlencode

from django.urls import reverse

from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent, Email, SMS
from corehq.apps.sms.tests.data_generator import (
    create_fake_sms,
    make_case_rule_sms_for_test,
    make_survey_sms_for_test,
    make_email_event_for_test,
    make_events_for_test
)
from corehq.apps.users.models import CommCareUser


class BaseMessagingEventResourceTest(APIResourceTest):
    @classmethod
    def _get_detail_endpoint(cls, event_id):
        return reverse('api_messaging_event_detail',
                       kwargs={"domain": cls.domain.name, "event_id": event_id, 'api_version': 'v1'})

    @classmethod
    def _get_list_endpoint(cls):
        return reverse('api_messaging_event_list', kwargs={"domain": cls.domain.name, 'api_version': 'v1'})

    def _auth_get_resource(self, url):
        return self._assert_auth_get_resource(url, allow_session_auth=True)


class TestMessagingEventResourceDetail(BaseMessagingEventResourceTest):
    def test_get_single(self):
        [sms] = _create_sms_messages(self.domain, 1, randomize=False)
        response = self._auth_get_resource(self._get_detail_endpoint(sms.messaging_subevent_id))
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertEqual(_serialized_messaging_event(sms), data)


class TestMessagingEventResource(BaseMessagingEventResourceTest):
    def test_get_list_simple(self):
        expected = []
        for sms in _create_sms_messages(self.domain, 2, randomize=False):
            expected.append(_serialized_messaging_event(sms))
        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(2, len(data))
        for result, expected_result in zip(data, expected):
            self.assertEqual(expected_result, result)

    def test_sms_null_date_modified(self):
        sms, _ = create_fake_sms(self.domain, randomize=False)
        # set date to None to simulate legacy data
        SMS.objects.filter(id=sms.id).update(date_modified=None)
        sms = SMS.objects.get(id=sms.id)
        self.assertIsNone(sms.date_modified)

        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(1, len(data))
        result = data[0]
        self.assertEqual(_serialized_messaging_event(sms), result)

    def test_date_last_activity_ordering(self):
        sms = _create_sms_messages(self.domain, 5, randomize=True)
        sms[0].messaging_subevent.save()  # this should move this one to the end of the list

        response = self._auth_get_resource(f'{self.list_endpoint}?order_by=date_last_activity')
        self.assertEqual(response.status_code, 200, response.content)
        ordered_data = json.loads(response.content)['objects']
        self.assertEqual(5, len(ordered_data))
        dates = [r['date_last_activity'] for r in ordered_data]
        expected_order = sms[1:] + [sms[0]]  # modification order
        self.assertEqual(dates, [s.messaging_subevent.date_last_activity.isoformat() for s in expected_order])

        response = self._auth_get_resource(f'{self.list_endpoint}?order_by=-date_last_activity')
        self.assertEqual(response.status_code, 200, response.content)
        reverse_ordered_data = json.loads(response.content)['objects']
        self.assertEqual(ordered_data, list(reversed(reverse_ordered_data)))

    def test_domain_filter(self):
        _create_sms_messages('different-one', 5, randomize=True)
        response = self._auth_get_resource(f'{self.list_endpoint}')
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(0, len(data))

    def test_source_filtering(self):
        sources = [
            MessagingEvent.SOURCE_BROADCAST, MessagingEvent.SOURCE_KEYWORD,
            MessagingEvent.SOURCE_REMINDER, MessagingEvent.SOURCE_UNRECOGNIZED,
            MessagingEvent.SOURCE_CASE_RULE
        ]
        for source in sources:
            make_events_for_test(self.domain.name, datetime.utcnow(), source=source)

        url = f'{self.list_endpoint}?source=keyword,reminder'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = {event["source"]["type"] for event in json.loads(response.content)['objects']}
        self.assertEqual(actual, {"keyword", "reminder", "conditional-alert"})

    def test_content_type_filtering(self):
        content_types = [
            MessagingEvent.CONTENT_SMS, MessagingEvent.CONTENT_EMAIL,
            MessagingEvent.CONTENT_API_SMS, MessagingEvent.CONTENT_IVR_SURVEY,
            MessagingEvent.CONTENT_SMS_SURVEY
        ]
        for content_type in content_types:
            make_events_for_test(self.domain.name, datetime.utcnow(), content_type=content_type)

        url = f'{self.list_endpoint}?content_type=ivr-survey,sms'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = {event["content_type"] for event in json.loads(response.content)['objects']}
        self.assertEqual(actual, {"sms", "api-sms", "ivr-survey"})

    def test_status_filtering_error(self):
        make_events_for_test(self.domain.name, datetime.utcnow())
        make_events_for_test(self.domain.name, datetime.utcnow(), status=MessagingEvent.STATUS_ERROR)
        make_events_for_test(self.domain.name, datetime.utcnow(), error=True)  # sms with error
        url = f'{self.list_endpoint}?status=error'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        events = json.loads(response.content)['objects']
        self.assertEqual(len(events), 2)
        actual = {event["status"] for event in events}
        self.assertEqual(actual, {"error"})

    def test_error_code_filtering(self):
        _create_sms_messages(self.domain, 2, True)
        e1 = MessagingSubEvent.objects.filter(domain=self.domain.name)[0]
        e1.error_code = MessagingEvent.ERROR_CANNOT_FIND_FORM
        e1.save()
        url = f'{self.list_endpoint}?error_code=CANNOT_FIND_FORM'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = {event["id"] for event in json.loads(response.content)['objects']}
        self.assertEqual(actual, {e1.id})

    def test_case_id_filter(self):
        _create_sms_messages(self.domain, 2, True)
        e1 = MessagingSubEvent.objects.filter(domain=self.domain.name)[0]
        e1.case_id = "123"
        e1.save()
        url = f'{self.list_endpoint}?case_id=123'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = {event["case_id"] for event in json.loads(response.content)['objects']}
        self.assertEqual(actual, {"123"})

    def test_contact_filter(self):
        user_ids = []
        for i in range(2):
            user = CommCareUser.create(
                self.domain.name, f"user {i}", "123", None, None, email=f"user{i}@email.com"
            )
            user_ids.append(user.get_id)
            self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        make_email_event_for_test(self.domain.name, "test broadcast", user_ids)
        make_events_for_test(self.domain.name, datetime.utcnow(), phone_number='+99912345678')
        _create_sms_messages(self.domain, 1, False)

        self._check_contact_filtering("email_address", "user0@email.com", "email_address")
        self._check_contact_filtering("email_address", "user1@email.com", "email_address")
        self._check_contact_filtering("phone_number", "+99912345678", "phone_number")

    def test_email_filter_validation(self):
        url = f'{self.list_endpoint}?email_address=not-an-email'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 400, response.content)

    def test_phone_number_filter_validation(self):
        url = f'{self.list_endpoint}?phone_number=not-an-phone-number'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 400, response.content)

    def _check_contact_filtering(self, key, value, field):
        query = urlencode({key: value.encode("utf8")})
        url = f'{self.list_endpoint}?{query}'
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = {event["messages"][0][field] for event in json.loads(response.content)['objects']}
        self.assertEqual(actual, {value})

    def test_case_rule(self):
        rule, event, sms = make_case_rule_sms_for_test(
            self.domain.name, "case rule name", datetime(2016, 1, 1, 12, 0))
        self.addCleanup(rule.delete)
        self.addCleanup(event.delete)  # cascades to subevent
        self.addCleanup(sms.delete)

        expected = {
            "case_id": None,
            "content_type": "sms",
            "date": "2016-01-01T12:00:00",
            "date_last_activity": event.date_last_activity.isoformat(),
            "domain": "qwerty",
            "error": None,
            "form": None,
            "messages": [
                {
                    "message_id": sms.id,
                    "backend": 'fake-backend-id',
                    "phone_number": "99912345678",
                    "content": "test sms text",
                    "date": "2016-01-01T12:00:00",
                    "date_modified": sms.date_modified.isoformat(),
                    "direction": "outgoing",
                    "status": "sent",
                    "type": "sms"
                }
            ],
            "recipient": {
                "name": "unknown",
                "recipient_id": "case_id_123",
                "type": "case"
            },
            "source": {
                "name": "case rule name",
                "type": "conditional-alert",
                "source_id": str(rule.id),
            },
            "status": "in-progress"
        }

        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(1, len(data))
        for result in data:
            del result['id']
            self.assertEqual(expected, result)

    def test_survey_sms(self):
        rule, xforms_session, event, sms = make_survey_sms_for_test(
            self.domain.name, "test sms survey", datetime(2016, 1, 1, 12, 0)
        )
        self.addCleanup(rule.delete)
        self.addCleanup(xforms_session.delete)
        self.addCleanup(event.delete)  # cascades to subevent
        self.addCleanup(sms.delete)

        subevent = event.subevents[0]

        expected = {
            "case_id": None,
            "content_type": "ivr-survey",
            "date": "2016-01-01T12:00:00",
            "date_last_activity": subevent.date_last_activity.isoformat(),
            "domain": "qwerty",
            "error": None,
            "form": {
                "app_id": "fake_app_id",
                "form_name": "fake form name",
                "form_submission_id": "fake_form_submission_id",
                "form_definition_id": "fake_form_id"
            },
            "messages": [
                {
                    "message_id": sms.id,
                    "backend": "fake-backend-id",
                    "phone_number": "99912345678",
                    "content": "test sms text",
                    "date": "2016-01-01T12:00:00",
                    "date_modified": sms.date_modified.isoformat(),
                    "direction": "outgoing",
                    "status": "sent",
                    "type": "ivr"
                }
            ],
            "recipient": {
                "name": "unknown",
                "recipient_id": "user_id_xyz",
                "type": "mobile-worker"
            },
            "source": {
                "name": "test sms survey",
                "type": "conditional-alert",
                "source_id": str(rule.id)
            },
            "status": "in-progress"
        }

        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(1, len(data))
        for result in data:
            del result['id']
            self.assertEqual(expected, result)

    def test_email(self):
        user = CommCareUser.create(self.domain.name, "bob", "123", None, None, email="bob@email.com")
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        events = make_email_event_for_test(self.domain.name, "test broadcast", [user.get_id])
        event = events[user.get_id]
        email = Email.objects.get(messaging_subevent=event)
        expected = {
            "case_id": None,
            "content_type": "email",
            "date": event.date.isoformat(),
            "date_last_activity": event.date_last_activity.isoformat(),
            "domain": "qwerty",
            "error": None,
            "form": None,
            "messages": [
                {
                    "message_id": email.id,
                    "backend": "email",
                    "email_address": "bob@email.com",
                    "content": "Check out the new API.",
                    "date": email.date.isoformat(),
                    "date_modified": email.date_modified.isoformat(),
                    "direction": "outgoing",
                    "status": "email-delivered",
                    "type": "email"
                }
            ],
            "recipient": {
                "name": "bob",
                "recipient_id": user.get_id,
                "type": "mobile-worker"
            },
            "source": {
                "name": "test broadcast",
                "type": "immediate-broadcast"
            },
            "status": "email-delivered"
        }

        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(1, len(data))
        for result in data:
            del result['id']
            del result['source']['source_id']
            self.assertEqual(expected, result)

    def test_email_null_date_modified(self):
        user = CommCareUser.create(self.domain.name, "bob", "123", None, None, email="bob@email.com")
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        events = make_email_event_for_test(self.domain.name, "test broadcast", [user.get_id])
        event = events[user.get_id]
        email = Email.objects.get(messaging_subevent=event)
        # set date to None to simulate legacy data
        Email.objects.filter(id=email.id).update(date_modified=None)

        response = self._auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)['objects']
        self.assertEqual(1, len(data))
        for result in data:
            self.assertEqual(result["date_last_activity"], event.date_last_activity.isoformat())
            self.assertIsNone(result["messages"][0]["date_modified"])

    def test_cursor(self):
        utcnow = datetime.utcnow()
        ids_and_dates = []
        for offset in range(5):
            date = utcnow + timedelta(hours=offset)
            _, subevent, _ = make_events_for_test(self.domain.name, date)
            ids_and_dates.append((subevent.id, date.isoformat()))

        content = self._test_cursor_response(ids_and_dates[:2], extra_params={
            "limit": 2, "order_by": "date_last_activity"})
        content = self._test_cursor_response(ids_and_dates[2:4], previous_content=content)
        self._test_cursor_response([ids_and_dates[-1]], previous_content=content)

    def test_cursor_descending_order(self):
        utcnow = datetime.utcnow()
        ids_and_dates = []
        for offset in range(5):
            date = utcnow + timedelta(hours=offset)
            _, subevent, _ = make_events_for_test(self.domain.name, date)
            ids_and_dates.append((subevent.id, date.isoformat()))

        ids_and_dates = list(reversed(ids_and_dates))

        content = self._test_cursor_response(ids_and_dates[:2], extra_params={
            "limit": 2, "order_by": "-date_last_activity"})
        content = self._test_cursor_response(ids_and_dates[2:4], previous_content=content)
        self._test_cursor_response([ids_and_dates[-1]], previous_content=content)

    def test_cursor_stuck_in_loop(self):
        """This demonstrates the limitation of the current cursor pagination implementation.
        If there are more objects with the same filter param than the batch size the API
        will get stuck in a loop.

        This should not be an issue for the message event API but is noted for completeness
        """

        utcnow = datetime.utcnow()
        ids_and_dates = []
        for i in range(5):
            _, subevent, _ = make_events_for_test(self.domain.name, utcnow)
            ids_and_dates.append((subevent.id, utcnow.isoformat()))

        content = self._test_cursor_response(ids_and_dates[:2], extra_params={"limit": 2})
        content = self._test_cursor_response(ids_and_dates[:2], previous_content=content)
        self._test_cursor_response(ids_and_dates[:2], previous_content=content)

    def test_cursor_multiple_matching_dates(self):
        """Make sure that where we have multiple objects with matching dates at the intersection of pages
        we return the correct result set.

        This works because we are sorting the results by 'event.date' AND 'event.id'
        """
        # events at 2, 3, 4 have the same dates ('[]' mark expected pages with limit=3)
        # [d1, d2, d3], [d3, d3, d4], [d5, d6]
        ids_and_dates = []
        previous_date = None
        for i in range(8):
            event_date = previous_date if i in (3, 4) else datetime.utcnow()
            previous_date = event_date
            _, subevent, _ = make_events_for_test(self.domain.name, event_date)
            ids_and_dates.append((subevent.id, event_date.isoformat()))

        content = self._test_cursor_response(ids_and_dates[:3], extra_params={"limit": 3})
        content = self._test_cursor_response(ids_and_dates[3:6], previous_content=content)
        self._test_cursor_response(ids_and_dates[6:], previous_content=content)

    def _test_cursor_response(self, expected, previous_content=None, extra_params=None):
        if previous_content:
            url = previous_content["meta"]["next"]
            assert not extra_params, "extra_params not allowed with previous_content"
        else:
            url = self.list_endpoint
            if extra_params:
                url = f'{url}?{urlencode(extra_params)}'

        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        content = json.loads(response.content)
        actual = [(event["id"], event["date"]) for event in content['objects']]
        self.assertEqual(actual, expected)
        if not expected:
            self.assertIsNone(content["meta"]["next"])
        return content


class DateFilteringTestMixin:
    field = None

    def test_date_filter_lt(self):
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.lt": dates[3].isoformat()
        }, [d.isoformat() for d in dates[:3]])

    def test_date_filter_lte(self):
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.lte": dates[3].isoformat()
        }, [d.isoformat() for d in dates[:4]])

    def test_date_filter_lte_date(self):
        """`lte` filter with a date (not datetime) should include data
        on that day."""
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.lte": str(dates[0].date())
        }, [d.isoformat() for d in dates])

    def test_date_filter_gt(self):
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.gt": dates[2].isoformat(),
        }, [d.isoformat() for d in dates[3:]])

    def test_date_filter_gte(self):
        """`gte` filter with a date (not datetime) should include data
        on that day."""
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.gte": dates[2].isoformat(),
        }, [d.isoformat() for d in dates[2:]])

    def test_date_filter_gte_date(self):
        dates = self._setup_for_date_filter_test()
        self._check_date_filtering_response({
            f"{self.field}.gte": str(dates[0].date())
        }, [d.isoformat() for d in dates])

    def _check_date_filtering_response(self, filters, expected):
        url = f'{self.list_endpoint}?order_by={self.field}&' + urllib.parse.urlencode(filters)
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = [event[self.field] for event in json.loads(response.content)['objects']]
        self.assertEqual(actual, expected)


class TestDateFilter(BaseMessagingEventResourceTest, DateFilteringTestMixin):
    field = "date"

    def _setup_for_date_filter_test(self):
        _create_sms_messages(self.domain, 5, randomize=True)
        return list(sorted(
            MessagingSubEvent.objects.filter(domain=self.domain.name)
            .values_list('date', flat=True)
        ))

    def _check_date_filtering_response(self, filters, expected):
        url = f'{self.list_endpoint}?' + urllib.parse.urlencode(filters)
        response = self._auth_get_resource(url)
        self.assertEqual(response.status_code, 200, response.content)
        actual = list(sorted(event["date"] for event in json.loads(response.content)['objects']))
        self.assertEqual(actual, expected)


class TestDateLastActivityFilter(BaseMessagingEventResourceTest, DateFilteringTestMixin):
    field = "date_last_activity"

    def test_email_date_last_activity_filtering(self):
        user_ids = []
        for i in range(5):
            user = CommCareUser.create(self.domain.name, f"bob{i}", "123", None, None, email=f"bob{i}@email.com")
            self.addCleanup(user.delete, self.domain.name, deleted_by=None)
            user_ids.append(user.get_id)
        events_by_user = make_email_event_for_test(self.domain.name, "test broadcast", user_ids)
        events = list(sorted(events_by_user.values(), key=attrgetter('date_last_activity')))
        events[0].save()  # update date_last_activity
        expected_order = events[1:] + [events[0]]  # modification order
        dates = [event.date_last_activity for event in expected_order]

        self._check_date_filtering_response({
            f"{self.field}.lt": dates[3].isoformat()
        }, [d.isoformat() for d in dates[:3]])

    def test_survey_date_last_activity_filter(self):
        events = []
        messages = []
        for i in range(5):
            rule, xforms_session, event, sms = make_survey_sms_for_test(
                self.domain.name, "test sms survey", datetime(2016, 1, 1, 12, 0)
            )
            self.addCleanup(rule.delete)
            self.addCleanup(xforms_session.delete)
            self.addCleanup(event.delete)  # cascades to subevent
            self.addCleanup(sms.delete)
            events.append(event.subevents[0])
            messages.append(sms)

        # update modified time for 1st session to move it to the end of the list
        events[0].save()

        expected_order = events[1:] + [events[0]]  # modification order
        dates = [event.date_last_activity for event in expected_order]

        self._check_date_filtering_response({
            f"{self.field}.lt": dates[3].isoformat()
        }, [d.isoformat() for d in dates[:3]])

    def _setup_for_date_filter_test(self):
        results = _create_sms_messages(self.domain, 5, randomize=True)
        results[0].messaging_subevent.save()  # update modification date
        expected_order = results[1:] + [results[0]]  # modification order
        return list(
            sms.messaging_subevent.date_last_activity for sms in expected_order
        )


def _create_sms_messages(domain, count, randomize):
    results = []
    for i in range(count):
        sms, _ = create_fake_sms(domain, randomize=randomize)
        results.append(sms)
    return results


def _serialized_messaging_event(sms):
    return {
        "id": sms.messaging_subevent_id,
        "content_type": "sms",
        "date": "2016-01-01T12:00:00",
        "date_last_activity": sms.messaging_subevent.date_last_activity.isoformat(),
        "case_id": None,
        "domain": "qwerty",
        "error": None,
        "form": None,
        'messages': [
            {
                'message_id': sms.id,
                'backend': 'fake-backend-id',
                'phone_number': '99912345678',
                'content': 'test sms text',
                'date': '2016-01-01T12:00:00',
                'date_modified': sms.date_modified.isoformat() if sms.date_modified else None,
                'direction': 'outgoing',
                'status': 'sent',
                'type': 'sms'
            }
        ],
        "recipient": {'name': 'unknown', 'recipient_id': None, 'type': 'case'},
        "source": {'source_id': None, 'name': 'sms', 'type': "other"},
        "status": "completed",
    }
