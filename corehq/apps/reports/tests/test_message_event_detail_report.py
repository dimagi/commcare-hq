import uuid
from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.standard.sms import MessageEventDetailReport
from corehq.apps.sms.tests.data_generator import (
    make_connect_message_event_for_test,
)
from corehq.apps.users.models import CommCareUser, WebUser
from dimagi.utils.dates import DateSpan


class TestMessageEventDetailReportConnectMessage(TestCase):
    domain = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.factory = RequestFactory()

        cls.web_user = WebUser.create(None, f'web-user-{cls.domain}', 'foobar', None, None)
        cls.web_user.add_domain_membership(cls.domain, is_admin=True)
        cls.web_user.save()
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)

        cls.recipient = CommCareUser.create(cls.domain, f'connect-recipient-{cls.domain}', 'foobar', None, None)
        cls.addClassCleanup(cls.recipient.delete, cls.domain, deleted_by=None)

    def test_row_uses_the_connect_message_log(self):
        event, __, __ = make_connect_message_event_for_test(
            self.domain, self.recipient.get_id, text='Check out the new API.'
        )

        row = self.get_report_row(event)

        assert row['Content'] == 'Check out the new API.'
        assert row['ConnectID'] == self.recipient.get_id
        assert row['Direction'] == 'Outgoing'
        assert row['Gateway'] == 'Connect Message'
        assert row['Status'] == 'Completed'

    def test_row_falls_back_to_placeholders_when_message_log_is_missing(self):
        # A subevent can exist without a ConnectMessage, e.g. when the send
        # failed before the message was logged.
        event, __, __ = make_connect_message_event_for_test(self.domain, self.recipient.get_id)

        row = self.get_report_row(event)

        assert row['Content'] == '-'
        assert row['ConnectID'] == '-'
        assert row['Direction'] == '-'
        assert row['Gateway'] == 'Connect Message'

    def get_report_row(self, event):
        request = self.factory.get('/', {'id': event.pk})
        request.couch_user = self.web_user
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=30),
            enddate=datetime.utcnow(),
        )
        report = MessageEventDetailReport(request, domain=self.domain)
        headers = [column.html for column in report.headers.header]
        rows = report.rows
        assert len(rows) == 1, rows
        return dict(zip(headers, [_cell_value(cell) for cell in rows[0]]))


def _cell_value(cell):
    return cell['html'] if isinstance(cell, dict) else cell
