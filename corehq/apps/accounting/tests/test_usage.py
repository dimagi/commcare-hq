import uuid

from django.test import TestCase

from corehq.apps.accounting.usage import get_web_usernames
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser


@es_test(requires=[user_adapter], setup_class=True)
class TestGetWebUsernames(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = [
            _web_user('active@example.com', ['domain-a']),
            _web_user('staff@dimagi.com', ['domain-a']),
            _web_user('two-domains@example.com', ['domain-a', 'domain-b']),
            _web_user('inactive-member@example.com', ['domain-a'], membership_active=False),
            _web_user('inactive-account@example.com', ['domain-a'], is_active=False),
            CommCareUser(_id=uuid.uuid4().hex, username='mobile', domain='domain-a', is_active=True),
        ]
        for user in users:
            user_adapter.index(user, refresh=True)

    def test_lists_active_web_users_including_dimagi(self):
        assert sorted(get_web_usernames('domain-a')) == [
            'active@example.com',
            'staff@dimagi.com',
            'two-domains@example.com',
        ]

    def test_user_in_two_domains_is_listed_in_each(self):
        assert 'two-domains@example.com' in get_web_usernames('domain-a')
        assert 'two-domains@example.com' in get_web_usernames('domain-b')

    def test_domain_without_web_users(self):
        assert get_web_usernames('domain-c') == []


def _web_user(username, domains, is_active=True, membership_active=True):
    return WebUser(
        _id=uuid.uuid4().hex,
        username=username,
        is_active=is_active,
        domains=domains,
        domain_memberships=[
            DomainMembership(domain=domain, is_active=membership_active) for domain in domains
        ],
    )
