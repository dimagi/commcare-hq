from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.case_importer.do_import import _is_valid_owner
from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser


class TestIsValidOwner(SimpleTestCase):

    def test_user_owner_match(self):
        self.assertTrue(_is_valid_owner(_mk_user(domain='match'), 'match'))

    def test_user_owner_nomatch(self):
        self.assertFalse(_is_valid_owner(_mk_user(domain='match'), 'nomatch'))

    def test_web_user_owner_match(self):
        self.assertTrue(_is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match'))
        self.assertTrue(_is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match2'))

    def test_web_user_owner_nomatch(self):
        self.assertFalse(_is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'nomatch'))


def _mk_user(domain):
    return CommCareUser(domain=domain, domain_membership=DomainMembership(domain=domain))


def _mk_web_user(domains):
    return WebUser(domains=domains, domain_memberships=[DomainMembership(domain=domain) for domain in domains])
