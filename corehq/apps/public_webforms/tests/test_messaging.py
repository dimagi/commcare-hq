from unittest import mock

from unmagic import fixture, use

from corehq.apps.public_webforms.messaging import send_one_time_link
from corehq.apps.public_webforms.tests.utils import (
    create_session,
    create_webform,
    webform_domain,
)


@fixture
def outbound():
    with (
        mock.patch(
            'corehq.apps.public_webforms.messaging.send_html_email_async.delay'
        ) as email,
        mock.patch('corehq.apps.public_webforms.messaging.send_sms') as sms,
    ):
        yield mock.Mock(email=email, sms=sms)


@use(webform_domain, outbound)
class TestSendOneTimeLink:

    def test_an_email_respondent_is_emailed(self):
        session = create_session(
            create_webform(), email='respondent@example.com')

        send_one_time_link(session, "Test Form Name")

        # send_html_email_async.delay(subject, recipient, html_content)
        email = outbound().email.call_args.args
        assert "Test Form Name" in email[0]
        assert email[1] == 'respondent@example.com'
        assert session.one_time_link in email[2]
        assert session.one_time_link in (
            outbound().email.call_args.kwargs['text_content'])

    def test_an_sms_respondent_is_texted(self):
        session = create_session(create_webform(), phone_number='15551234567')

        send_one_time_link(session, "Test Form Name")

        # send_sms(domain, contact, phone_number, text)
        sms = outbound().sms.call_args.args
        assert sms[1] is None  # the respondent is nobody this project knows
        assert sms[2] == '15551234567'
        assert "Test Form Name" in sms[3]
        assert session.one_time_link in sms[3]
