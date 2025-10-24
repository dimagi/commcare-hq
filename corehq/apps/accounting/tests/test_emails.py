import datetime
from unittest.mock import patch

from time_machine import travel

from dimagi.utils.web import get_site_domain

from corehq.apps.accounting.emails import (
    _ending_reminder_context,
    _get_reminder_email_contacts,
)
from corehq.apps.accounting.models import WebUser
from corehq.apps.accounting.tests.base_tests import BaseInvoiceTestCase
from corehq.apps.domain.views.accounting import DomainSubscriptionView
from corehq.const import USER_DATE_FORMAT
from corehq.util.view_utils import absolute_reverse


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


class TestEndingReminderContext(BaseInvoiceTestCase):

    @travel('2025-10-01', tick=False)
    def test_ending_reminder_context(self):
        self.subscription.date_end = datetime.date(2025, 10, 31)
        self.subscription.save()

        user_formatted_date = self.subscription.date_end.strftime(USER_DATE_FORMAT)
        context = _ending_reminder_context(self.subscription, 30)
        assert context['domain'] == self.domain.name
        assert context['plan_name'] == self.subscription.plan_version.plan.name
        assert context['account'] == self.account.name
        assert context['ending_on'] == f"on {user_formatted_date}."
        assert context['subscription_url'] == absolute_reverse(
            DomainSubscriptionView.urlname, args=[self.domain.name]
        )
        assert context['base_url'] == get_site_domain()
        assert context['subject'] == (
            f"CommCare Alert: {self.domain.name}'s subscription to {self.subscription.plan_version.plan.name} "
            f"ends on {user_formatted_date}."
        )

    @travel('2025-10-01', tick=False)
    def test_ending_on_tomorrow_if_one_day_left(self):
        self.subscription.date_end = datetime.date(2025, 10, 2)
        self.subscription.save()

        context = _ending_reminder_context(self.subscription, 1)
        assert context['ending_on'] == "tomorrow!"

    @travel('2025-10-01', tick=False)
    def test_subject_uses_account_if_customer_billing_account(self):
        self.subscription.account.is_customer_billing_account = True
        self.subscription.account.save()
        self.subscription.date_end = datetime.date(2025, 10, 31)
        self.subscription.save()

        user_formatted_date = self.subscription.date_end.strftime(USER_DATE_FORMAT)
        context = _ending_reminder_context(self.subscription, 30)
        assert context['subject'] == (
            f"CommCare Alert: {self.account.name}'s subscription to {self.subscription.plan_version.plan.name} "
            f"ends on {user_formatted_date}."
        )
