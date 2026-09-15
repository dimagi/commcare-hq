import re
from unittest import mock

import pytest
from unmagic import fixture, use

from corehq.apps.public_webforms.messaging import (
    MAX_SMS_FORM_NAME_LENGTH,
    _truncate_for_sms,
    send_one_time_link,
)
from corehq.apps.public_webforms.tests.utils import (
    create_session,
    create_webform,
    webform_domain,
)
from corehq.apps.short_links.models import ShortLink


def short_link_in(text):
    return ShortLink.objects.get(code=re.search(r'/s/(\w+)', text).group(1))


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
        assert session.one_time_link not in sms[3]
        assert short_link_in(sms[3]).target_url == session.one_time_link

    def test_a_long_form_name_is_truncated_in_the_message(self):
        session = create_session(create_webform(), phone_number='15551234567')

        send_one_time_link(
            session, "Maternal Health Screening and Follow-Up Visit Form")

        sms = outbound().sms.call_args.args
        assert "Maternal Health Screening and Follow-Up Vi..." in sms[3]


@pytest.mark.parametrize('form_name, expected', [
    ('Postnatal Visit', 'Postnatal Visit'),
    ('M' * MAX_SMS_FORM_NAME_LENGTH, 'M' * MAX_SMS_FORM_NAME_LENGTH),
    ('M' * (MAX_SMS_FORM_NAME_LENGTH + 1), 'M' * 42 + '...'),
])
def test_a_form_name_is_truncated_only_past_the_cap(form_name, expected):
    assert _truncate_for_sms(form_name) == expected
