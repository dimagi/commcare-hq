from __future__ import print_function, unicode_literals

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.dashboard.views import NewUserDashboardView
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain, TransferDomainRequest
from corehq.apps.domain.forms import TransferDomainForm, TransferDomainFormErrors
from corehq.apps.domain.views import TransferDomainView
from corehq.apps.domain.exceptions import InactiveTransferDomainException

class BaseDomainTest(TestCase):
    def setUp(self):
        self.client = Client()

        self.domain = Domain(name="fandago", is_active=True)
        self.domain.save()

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

        self.mugglename = 'muggle'
        self.muggle = WebUser.create('anotherdomain', self.mugglename, self.password)
        self.muggle.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()
        self.muggle.delete()

class TestTransferDomainForm(BaseDomainTest):

    def test_valid_data(self):
        data = {
            'to_username': self.mugglename,
            'domain': self.domain.name,
        }

        form = TransferDomainForm(self.domain.name, self.user.username, data)

        self.assertTrue(form.is_valid(), form.errors)

        transfer = form.save()
        self.assertEqual(transfer.to_username, self.mugglename)
        self.assertEqual(transfer.domain, self.domain.name)
        self.assertEqual(transfer.from_username, self.username)

    def test_invalid_user_data(self):
        data = {
            'to_username': 'non-existant',
            'domain': 'mismatch',
        }

        form = TransferDomainForm(self.domain.name, self.user.username, data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'to_username': [TransferDomainFormErrors.USER_DNE],
            'domain': [TransferDomainFormErrors.DOMAIN_MISMATCH],
        })

class TestTransferDomainModel(BaseDomainTest):

    def setUp(self):
        super(TestTransferDomainModel, self).setUp()

        self.transfer = TransferDomainRequest(
            to_username=self.mugglename,
            from_username=self.username,
            domain=self.domain.name)
        self.transfer.save()

    def tearDown(self):
        super(TestTransferDomainModel, self).tearDown()

        self.transfer.delete()

    def test_domain_transfer_inactive(self):
        self.transfer.active = False
        self.transfer.save()

        with self.assertRaises(InactiveTransferDomainException):
            self.transfer.transfer_domain()

        with self.assertRaises(InactiveTransferDomainException):
            self.transfer.send_transfer_request()

    def test_domain_transfer(self):
        self.transfer.transfer_domain()

        self.assertFalse(self.transfer.active)
        self.assertFalse(self.transfer.from_user.is_member_of(self.domain))
        self.assertTrue(self.transfer.to_user.is_member_of(self.domain))

    def test_send_transfer_request(self):
        self.transfer.send_transfer_request()

        self.assertIsNotNone(self.transfer.transfer_guid)
        self.assertEqual(len(mail.outbox), 2,
                         "Should send an email to both requester and requestee")


