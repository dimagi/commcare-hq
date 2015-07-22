from __future__ import print_function, unicode_literals
from datetime import datetime

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq import toggles
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
        toggles.TRANSFER_DOMAIN.set("domain:{domain}".format(domain=self.domain.name), True)

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

        self.another_domain = Domain(name='anotherdomain', is_active=True)
        self.another_domain.save()
        self.mugglename = 'muggle'
        self.muggle = WebUser.create(self.another_domain.name, self.mugglename, self.password)
        self.muggle.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()
        self.muggle.delete()
        self.another_domain.delete()


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

    def test_get_active_transfer(self):
        res = TransferDomainRequest.get_active_transfer(self.domain, self.user.username)
        self.assertIsNotNone(res)

        newer = TransferDomainRequest(
            to_username=self.mugglename,
            from_username=self.username,
            request_time=datetime.utcnow(),
            domain=self.domain.name)
        newer.save()

        res = TransferDomainRequest.get_active_transfer(self.domain, self.user.username)
        self.assertEqual(res.pk, newer.pk)
        self.assertFalse(TransferDomainRequest.objects.get(pk=self.transfer.pk).active)


class TestTransferDomainViews(BaseDomainTest):
    def setUp(self):
        super(TestTransferDomainViews, self).setUp()
        self.transfer = TransferDomainRequest(
            to_username=self.mugglename,
            from_username=self.username,
            domain=self.domain.name)
        self.transfer.save()
        self.transfer.send_transfer_request()

        self.rando = WebUser.create(self.domain.name, 'rando', self.password)

    def tearDown(self):
        super(TestTransferDomainViews, self).tearDown()
        self.transfer.delete()
        self.rando.delete()

    def test_permissions_for_activation(self):
        # No one logged in
        resp = self.client.post(reverse('activate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.template_name, 'login_and_password/login.html',
                         'Should redirect to login page')

        # Initiator logged in
        self.client.login(username=self.username, password=self.password)
        resp = self.client.post(reverse('activate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.status_code, 403)

        # Accepter logged in
        self.client.login(username=self.mugglename, password=self.password)
        resp = self.client.post(reverse('activate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_permissions_for_deactivation(self):
        # No one logged in
        resp = self.client.post(reverse('deactivate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.template_name, 'login_and_password/login.html',
                         'Should redirect to login page')

        # Random user who belongs to the domain
        self.client.login(username=self.rando.username, password=self.password)
        resp = self.client.post(reverse('deactivate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.status_code, 403)

        # Accepter logged in
        self.client.login(username=self.mugglename, password=self.password)
        resp = self.client.post(reverse('deactivate_transfer_domain',
                                        args=[self.transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_permissions_for_transfer_domain_view(self):
        # No one logged in
        resp = self.client.get(reverse('transfer_domain_view',
                                       args=[self.domain.name]), follow=True)
        self.assertRedirects(resp, reverse('domain_login', kwargs={'domain': self.domain.name}) +
            '?next=' + reverse('transfer_domain_view', args=[self.domain.name]))

        # Random user who belongs to the domain but not an admin
        self.client.login(username=self.rando.username, password=self.password)
        resp = self.client.get(reverse('transfer_domain_view',
                                       args=[self.domain.name]))
        self.assertEqual(resp.status_code, 302, 'Should redirect to dashboard')

        # Domain admin logged in
        self.client.login(username=self.user.username, password=self.password)
        resp = self.client.get(reverse('transfer_domain_view',
                                       args=[self.domain.name]))
        self.assertEqual(resp.status_code, 200)


class TestTransferDomainIntegration(BaseDomainTest):

    def setUp(self):
        super(TestTransferDomainIntegration, self).setUp()

        self.client.login(username=self.username, password=self.password)

    def test_basic_workflow(self):
        """
        This should execute a basic transferring of domains. user will transfer a
        domain to muggle. user should be able to see status of transferred domain
        and muggle will accept transfer request.
        """

        # Get the transfer request page
        resp = self.client.get(reverse(TransferDomainView.urlname, args=[self.domain.name]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(type(resp.context['form']), TransferDomainForm,
                         "Should get TransferRequestForm")

        form = resp.context['form']
        form.data['domain'] = self.domain.name
        form.data['to_username'] = self.muggle.username

        # Post the form data
        resp = self.client.post(reverse(TransferDomainView.urlname, args=[self.domain.name]),
                                form.data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 2,
                         "Should send an email to both requester and requestee")

        transfer = TransferDomainRequest.objects.get(to_username=self.muggle.username,
                                                     from_username=self.user.username,
                                                     domain=self.domain.name)
        self.assertIsNotNone(transfer)
        self.assertIsNone(transfer.confirm_time)
        self.assertTrue(transfer.active)

        # Land on the activate transfer page
        self.client.login(username=self.muggle.username, password=self.password)
        resp = self.client.get(reverse('activate_transfer_domain', args=[transfer.transfer_guid]), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['transfer'])

        # Finally accept the transfer
        mail.outbox = []  # Clear outbox
        resp = self.client.post(reverse('activate_transfer_domain', args=[transfer.transfer_guid]), follow=True)
        self.assertEqual(len(mail.outbox), 1, "Send an email to Dimagi to confirm")

        # Reload from DB
        user = WebUser.get_by_username(self.user.username)
        muggle = WebUser.get_by_username(self.muggle.username)
        transfer = TransferDomainRequest.objects.get(to_username=self.muggle.username,
                                                     from_username=self.user.username,
                                                     domain=self.domain.name)
        self.assertFalse(user.is_member_of(self.domain.name))
        self.assertTrue(muggle.is_member_of(self.domain.name))
        self.assertTrue(muggle.get_domain_membership(self.domain.name).is_admin)
        self.assertIsNotNone(transfer.confirm_time)

    def test_transfer_cancel_workflow(self):
        """
        This should execute a transferring of domains, but have the user cancel the request
        before the other user accepts that request
        """

        data = {
            'domain': self.domain.name,
            'to_username': self.muggle.username,
        }

        # Post the transfer data
        resp = self.client.post(reverse(TransferDomainView.urlname, args=[self.domain.name]), data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Ensure transfer is active
        transfer = TransferDomainRequest.get_active_transfer(self.domain.name, self.user.username)
        self.assertIsNotNone(transfer)

        # Deactivate transfer request before to_user accepts the transfer
        resp = self.client.post(reverse('deactivate_transfer_domain', args=[transfer.transfer_guid]))

        # Ensure transfer is now deactivated
        updated_transfer = TransferDomainRequest.get_active_transfer(self.domain.name, self.user.username)
        self.assertIsNone(updated_transfer)

        # Attempt to activate transfer
        self.client.login(username=self.muggle.username, password=self.password)
        resp = self.client.post(reverse('activate_transfer_domain', args=[transfer.transfer_guid]))
        self.assertEqual(resp.status_code, 404)
