from unittest import mock

from unmagic import fixture, use

from corehq.apps.public_webforms.messaging import send_one_time_link
from corehq.apps.public_webforms.tests.utils import (
    DOMAIN,
    create_session,
    create_webform,
    webform_domain,
)

FORM_NAME = 'Antenatal Visit'


@fixture
def outbound():
    """Stands in for the email and SMS gateways."""
    with (
        mock.patch('corehq.apps.public_webforms.messaging'
                   '.send_html_email_async.delay') as email,
        mock.patch('corehq.apps.public_webforms.messaging.send_sms') as sms,
    ):
        yield mock.Mock(email=email, sms=sms)


@use(webform_domain, outbound)
class TestSendOneTimeLink:

    def test_an_email_respondent_is_emailed(self):
        session = create_session(
            create_webform(), email='respondent@example.com')

        send_one_time_link(session, FORM_NAME)

        subject, recipient, __ = outbound().email.call_args.args
        assert recipient == 'respondent@example.com'
        assert FORM_NAME in subject
        assert not outbound().sms.called

    def test_an_sms_respondent_is_texted(self):
        session = create_session(create_webform(), phone_number='15551234567')

        send_one_time_link(session, FORM_NAME)

        __, contact, phone_number, text = outbound().sms.call_args.args
        assert phone_number == '15551234567'
        assert contact is None  # the respondent is nobody this project knows
        assert FORM_NAME in text
        assert not outbound().email.called

    def test_the_link_carries_the_session_id_and_never_its_key(self):
        session = create_session(create_webform(), phone_number='15551234567')

        send_one_time_link(session, FORM_NAME)

        __, __, __, text = outbound().sms.call_args.args
        assert session.id.hex in text
        assert session.session_key.hex not in text

    def test_the_email_names_the_form_and_the_project(self):
        session = create_session(
            create_webform(), email='respondent@example.com')

        send_one_time_link(session, FORM_NAME)

        __, __, html = outbound().email.call_args.args
        text = outbound().email.call_args.kwargs['text_content']
        for body in (html, text):
            assert FORM_NAME in body
            assert DOMAIN in body
            # a respondent should know where what they submit is going
            assert 'may be seen by' in body
