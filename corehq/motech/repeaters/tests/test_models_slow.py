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
from corehq.motech.repeaters.models import FormRepeater, send_request
from corehq.util.test_utils import timelimit

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class ServerErrorTests(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(clear_plan_version_cache)
        cls.domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.addClassCleanup(cls.teardown_subscriptions)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

        url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        cls.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        cls.repeater.save()
        cls.instance_id = str(uuid4())
        post_xform(cls.instance_id)

    def setUp(self):
        super().setUp()
        self.repeater = self.reget_repeater()
        self.repeat_record = self.repeater.repeat_records.create(
            domain=DOMAIN,
            payload_id=self.instance_id,
            registered_at=timezone.now(),
        )

    def reget_repeater(self):
        return FormRepeater.objects.get(pk=self.repeater.pk)

    def test_success_on_200(self):
        resp = ResponseMock(status_code=200, reason='OK')
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_SUCCESS_STATE)
            repeater = self.reget_repeater()
            self.assertIsNone(repeater.next_attempt_at)

    def test_no_backoff_on_409(self):
        resp = ResponseMock(status_code=409, reason='Conflict')
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater = self.reget_repeater()
            # Trying tomorrow is just as likely to work as in 5 minutes
            self.assertIsNone(repeater.next_attempt_at)

    def test_no_backoff_on_500(self):
        resp = ResponseMock(status_code=500, reason='Internal Server Error')
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater = self.reget_repeater()
            self.assertIsNone(repeater.next_attempt_at)

    @timelimit(65)
    def test_backoff_on_503(self):
        """Configured with a custom timelimit to prevent intermittent test
        failures in GitHub actions. Example:

        ```
        setup,corehq.motech.repeaters.tests.test_models_slow:ServerErrorTests.test_backoff_on_503,60.48151421546936,1673364559.7436702
        ERROR

        ======================================================================
        ERROR: corehq.motech.repeaters.tests.test_models_slow:ServerErrorTests.test_backoff_on_503
        ----------------------------------------------------------------------
        Traceback (most recent call last):
        File "/vendor/lib/python3.9/site-packages/nose/case.py", line 134, in run
            self.runTest(result)
        File "/vendor/lib/python3.9/site-packages/nose/case.py", line 152, in runTest
            test(result)
        File "/vendor/lib/python3.9/site-packages/django/test/testcases.py", line 245, in __call__
            self._setup_and_call(result)
        File "/vendor/lib/python3.9/site-packages/django/test/testcases.py", line 281, in _setup_and_call
            super().__call__(result)
        AssertionError: setup time limit (29.0) exceeded: 60.48151421546936
        ```
        """
        resp = ResponseMock(status_code=503, reason='Service Unavailable')
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.return_value = resp

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater = self.reget_repeater()
            self.assertIsNotNone(repeater.next_attempt_at)

    def test_backoff_on_connection_error(self):
        with patch('corehq.motech.repeaters.models.simple_request') as simple_request:
            simple_request.side_effect = ConnectionError()

            payload = self.repeater.get_payload(self.repeat_record)
            send_request(self.repeater, self.repeat_record, payload)

            self.assertEqual(self.repeat_record.attempts.last().state,
                             RECORD_FAILURE_STATE)
            repeater = self.reget_repeater()
            self.assertIsNotNone(repeater.next_attempt_at)


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
