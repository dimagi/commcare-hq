import random
import string
from collections import namedtuple
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from requests.exceptions import ConnectionError

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.const import (
    RECORD_FAILURE_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.models import (
    FormRepeater,
    SQLRepeater,
    send_request,
)

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class ServerErrorTests(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        cls.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        cls.repeater.save()
        cls.sql_repeater = SQLRepeater.objects.create(
            domain=DOMAIN,
            repeater_id=cls.repeater.get_id,
        )
        cls.instance_id = str(uuid4())
        post_xform(cls.instance_id)

    @classmethod
    def tearDownClass(cls):
        cls.sql_repeater.delete()
        cls.repeater.delete()
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.repeat_record = self.sql_repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id=self.instance_id,
            registered_at=timezone.now(),
        )

    def tearDown(self):
        self.repeat_record.delete()
        super().tearDown()

    def reget_sql_repeater(self):
        return SQLRepeater.objects.get(pk=self.sql_repeater.pk)

    def test_success_on_200(self):
        resp = ResponseMock(status_code=200, reason='OK')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_SUCCESS_STATE)
            sql_repeater = self.reget_sql_repeater()
            self.assertIsNone(sql_repeater.next_attempt_at)

    def test_no_backoff_on_409(self):
        resp = ResponseMock(status_code=409, reason='Conflict')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            sql_repeater = self.reget_sql_repeater()
            # Trying tomorrow is just as likely to work as in 5 minutes
            self.assertIsNone(sql_repeater.next_attempt_at)

    def test_no_backoff_on_500(self):
        resp = ResponseMock(status_code=500, reason='Internal Server Error')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            sql_repeater = self.reget_sql_repeater()
            self.assertIsNone(sql_repeater.next_attempt_at)

    def test_backoff_on_503(self):
        resp = ResponseMock(status_code=503, reason='Service Unavailable')
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            sql_repeater = self.reget_sql_repeater()
            self.assertIsNotNone(sql_repeater.next_attempt_at)

    def test_backoff_on_connection_error(self):
        with patch('corehq.motech.repeaters.models.simple_post') as simple_post:
            simple_post.side_effect = ConnectionError()

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            sql_repeater = self.reget_sql_repeater()
            self.assertIsNotNone(sql_repeater.next_attempt_at)


def post_xform(instance_id):
    xform = f"""<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
      xmlns="https://www.commcarehq.org/test/ServerErrorTests/">
    <foo/>
    <bar/>
    <meta>
        <deviceID>ServerErrorTests</deviceID>
        <timeStart>2011-10-01T15:25:18.404-04</timeStart>
        <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
        <username>admin</username>
        <userID>testy.mctestface</userID>
        <instanceID>{instance_id}</instanceID>
    </meta>
</data>
"""
    submit_form_locally(xform, DOMAIN)
