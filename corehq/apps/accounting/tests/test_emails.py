from unittest.mock import patch

from corehq.apps.accounting.emails import (
    _get_reminder_email_contacts,
)
from corehq.apps.accounting.models import WebUser
from corehq.apps.accounting.tests.base_tests import BaseInvoiceTestCase


class TestGetReminderEmailContacts(BaseInvoiceTestCase):
    def test_get_reminder_email_contacts(self):
        billing_contacts = ['amanda@example.com', 'bob@example.com']
        self.account.billingcontactinfo.email_list = billing_contacts
        self.account.billingcontactinfo.save()

        project_admins = ['carly@example.com', 'dave@example.com']
        for email in project_admins:
            user = WebUser.create(self.domain.name, email, 'test123', None, None, email)
            user.set_role(self.domain.name, 'admin')
            user.save()

        dimagi_users = ['eliza@dimagi.com', 'fred@dimagi.com']
        for email in dimagi_users:
            WebUser.create(self.domain.name, email, 'test123', None, None, email=email)

        dimagi_account_contact = 'ginny@example.com'
        self.account.dimagi_contact = dimagi_account_contact

        to, cc, bcc = _get_reminder_email_contacts(self.subscription, self.domain.name)
        assert to == set(billing_contacts)
        assert cc == set(project_admins)
        assert bcc == set(dimagi_users + [dimagi_account_contact])

    def test_contacts_only_in_one_list(self):
        billing_contacts = ['amanda@dimagi.com']
        self.account.billingcontactinfo.email_list = billing_contacts
        self.account.billingcontactinfo.save()

        project_admins = ['amanda@dimagi.com', 'bob@dimagi.com']
        for email in project_admins:
            user = WebUser.create(self.domain.name, email, 'test123', None, None, email=email)
            user.set_role(self.domain.name, 'admin')
            user.save()

        # also add a non-admin Dimagi user
        WebUser.create(
            self.domain.name, 'carly@dimagi.com', 'test123', None, None, email='carly@dimagi.com'
        )

        to, cc, bcc = _get_reminder_email_contacts(self.subscription, self.domain.name)
        assert to == set(['amanda@dimagi.com'])
        assert cc == set(['bob@dimagi.com'])
        assert bcc == set(['carly@dimagi.com'])

    def test_to_project_admins_if_no_billing_contact(self):
        # this shouldn't normally happen, but is possible with older billing accounts
        self.account.billingcontactinfo.email_list = ''
        self.account.billingcontactinfo.save()

        project_admins = ['carly@example.com', 'dave@example.com']
        for email in project_admins:
            user = WebUser.create(self.domain.name, email, 'test123', None, None, email)
            user.set_role(self.domain.name, 'admin')
            user.save()

        dimagi_users = ['eliza@dimagi.com', 'fred@dimagi.com']
        for email in dimagi_users:
            WebUser.create(self.domain.name, email, 'test123', None, None, email=email)

        dimagi_account_contact = 'ginny@example.com'
        self.account.dimagi_contact = dimagi_account_contact

        with patch('corehq.apps.accounting.emails._soft_assert_contact_emails_missing') as soft_assert:
            to, cc, bcc = _get_reminder_email_contacts(self.subscription, self.domain.name)
            soft_assert.assert_called_once
            assert to == set(project_admins)
            assert cc is None
            assert bcc == set(dimagi_users + [dimagi_account_contact])
