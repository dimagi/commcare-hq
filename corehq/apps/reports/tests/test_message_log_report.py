from __future__ import absolute_import, unicode_literals

import uuid
from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import RequestFactory

from dimagi.utils.dates import DateSpan

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.standard.sms import MessageLogReport
from corehq.apps.sms.models import OUTGOING, SMS, MessagingEvent
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled
from six.moves import zip


@flag_enabled('SMS_LOG_CHANGES')
class MessageLogReportTest(TestCase):
    domain = uuid.uuid4().hex

    def test_basic_functionality(self):
        self.make_simple_sms('message 1')
        self.make_simple_sms('message 2')
        self.assertEqual(
            self.get_report_column('Message'),
            ['message 1', 'message 2'],
        )

    def test_event_column(self):
        self.make_simple_sms('message')
        self.make_case_rule_sms('Rule 2')
        # This sms tests this particular condition
        self.make_survey_sms('Rule 3')

        for report_value, rule_name in zip(
            self.get_report_column('Event'),
            ['-', 'Rule 2', 'Rule 3'],
        ):
            # The cell value should be a link to the rule
            self.assertIn(rule_name, report_value)

    def test_include_erroring_sms_status(self):
        self.make_simple_sms('message 1', error_message=SMS.ERROR_INVALID_DIRECTION)
        self.make_simple_sms('message 2')
        self.assertEqual(
            self.get_report_column('Status'),
            ['Error - Unknown message direction.', 'Sent'],
        )

    @classmethod
    def setUpClass(cls):
        super(MessageLogReportTest, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.factory = RequestFactory()
        cls.couch_user = WebUser.create(None, "phone_report_test", "foobar")
        cls.couch_user.add_domain_membership(cls.domain, is_admin=True)
        cls.couch_user.save()

    @classmethod
    def tearDownClass(cls):
        super(MessageLogReportTest, cls).tearDownClass()
        cls.couch_user.delete()
        cls.domain_obj.delete()

    def get_report_column(self, column_header):
        return [row[column_header] for row in self.get_report_rows()]

    def get_report_rows(self):
        request = self.factory.get('/')
        request.couch_user = self.couch_user
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=30),
            enddate=datetime.utcnow(),
        )
        report = MessageLogReport(request, domain=self.domain)
        headers = [h.html for h in report.headers.header]
        for row in report.export_rows:
            yield dict(zip(headers, row))

    def make_simple_sms(self, message, error_message=None):
        sms = SMS.objects.create(
            domain=self.domain,
            date=datetime.utcnow(),
            direction=OUTGOING,
            text=message,
            error=bool(error_message),
            system_error_message=error_message,
        )
        self.addCleanup(sms.delete)

    def make_case_rule_sms(self, rule_name):
        rule = AutomaticUpdateRule.objects.create(domain=self.domain, name=rule_name)
        event = MessagingEvent.objects.create(
            domain=self.domain,
            date=datetime.utcnow(),
            source=MessagingEvent.SOURCE_CASE_RULE,
            source_id=rule.pk,
        )
        subevent = event.create_subevent_for_single_sms()
        sms = SMS.objects.create(
            domain=self.domain,
            date=datetime.utcnow(),
            direction=OUTGOING,
            text='this is a message',
            messaging_subevent=subevent,
        )
        self.addCleanup(rule.delete)
        self.addCleanup(event.delete)  # cascades to subevent
        self.addCleanup(sms.delete)

    def make_survey_sms(self, rule_name):
        # It appears that in production, many SMSs don't have a direct link to the
        # triggering event - the connection is roundabout via the xforms_session
        rule = AutomaticUpdateRule.objects.create(domain=self.domain, name=rule_name)
        xforms_session = SQLXFormsSession.objects.create(
            domain=self.domain,
            couch_id=uuid.uuid4().hex,
            start_time=datetime.utcnow(),
            modified_time=datetime.utcnow(),
            current_action_due=datetime.utcnow(),
            expire_after=3,
        )
        event = MessagingEvent.objects.create(
            domain=self.domain,
            date=datetime.utcnow(),
            source=MessagingEvent.SOURCE_CASE_RULE,
            source_id=rule.pk,
        )
        subevent = event.create_subevent_for_single_sms()
        subevent.xforms_session = xforms_session
        subevent.save()
        sms = SMS.objects.create(
            domain=self.domain,
            date=datetime.utcnow(),
            direction=OUTGOING,
            text='this is a message',
            xforms_session_couch_id=xforms_session.couch_id,
        )
        self.addCleanup(rule.delete)
        self.addCleanup(xforms_session.delete)
        self.addCleanup(event.delete)  # cascades to subevent
        self.addCleanup(sms.delete)
