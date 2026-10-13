from django.test import RequestFactory

import pytest

from corehq.apps.domain.models import ChatbotDomainSettings
from corehq.apps.hqwebapp.chat_access import chatbot_enabled_for_request
from corehq.apps.users.models import DomainMembership, WebUser
from corehq.util.test_utils import flag_enabled, flag_disabled


@pytest.mark.django_db
@pytest.mark.parametrize(('opted_out', 'expected'), [
    (False, True),
    (True, False),
])
@flag_enabled('GA_OCS_CHATBOT')
def test_ga_respects_domain_opt_out(opted_out, expected):
    ChatbotDomainSettings.objects.create(domain='project', disabled=opted_out)
    _assert_enabled(_request(), expected)


@pytest.mark.django_db
@pytest.mark.parametrize(('preview_on', 'expected'), [
    (True, True),
    (False, False),
])
@flag_disabled('GA_OCS_CHATBOT')
def test_preview_controls_access_when_not_ga(preview_on, expected):
    preview = flag_enabled if preview_on else flag_disabled
    with preview('OCS_CHATBOT', is_preview=True):
        _assert_enabled(_request(), expected)


@pytest.mark.django_db
@flag_disabled('GA_OCS_CHATBOT')
@flag_enabled('OCS_CHATBOT', is_preview=True)
def test_opt_out_is_ignored_with_ga_disabled():
    ChatbotDomainSettings.objects.create(domain='project', disabled=True)
    _assert_enabled(_request(), True)


def _request(domain='project'):
    request = RequestFactory().get('/')
    request.domain = domain
    request.couch_user = WebUser(domain_memberships=[DomainMembership(domain=domain)])
    return request


def _assert_enabled(request, expected):
    assert chatbot_enabled_for_request(request) is expected
