from django.test import TestCase
import mock

from django.conf import settings
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.registration.utils import handle_changed_mailchimp_email


class UtilTestCase(TestCase):

    def setUp(self):
        self.username = "joe@my-domain.commcarehq.org"
        self.email = "email@example.com"
        password = "password"
        self.domain = 'my-domain'
        self.couch_user = CommCareUser.create(self.domain, self.username, password, email=self.email)
        self.couch_user.subscribed_to_commcare_users = True
        self.couch_user.email_opt_out = False
        self.couch_user.save()

    def tearDown(self):
        for user in CouchUser.all():
            user.delete()
        User.objects.all().delete()

    @mock.patch("corehq.apps.registration.utils.safe_unsubscribe_user_from_mailchimp_list")
    def test_handle_changed_mailchimp_email_unsubscribe(self, unsubscribe):
        """ Only one user with this email, unsubscribe it from both """

        new_email = "newemail@example.com"

        handle_changed_mailchimp_email(self.couch_user, self.email, new_email)

        expected_call_args = [mock.call(self.couch_user, settings.MAILCHIMP_COMMCARE_USERS_ID, email=self.email),
                              mock.call(self.couch_user, settings.MAILCHIMP_MASS_EMAIL_ID, email=self.email)]

        self.assertEqual(unsubscribe.call_count, 2)
        self.assertItemsEqual(unsubscribe.call_args_list, expected_call_args)

    @mock.patch("corehq.apps.registration.utils.safe_unsubscribe_user_from_mailchimp_list")
    def test_handle_changed_mailchimp_email_dont_unsubscribe(self, unsubscribe):
        """ Two users with the same email, dont unsubscribe """

        other_username = "shmoe@my-domain.commcarehq.org"
        other_couch_user = CommCareUser.create(self.domain, other_username, "passw3rd", email=self.email)
        other_couch_user.subscribed_to_commcare_users = True
        other_couch_user.email_opt_out = False
        other_couch_user.save()

        new_email = "newemail@example.com"

        handle_changed_mailchimp_email(self.couch_user, self.email, new_email)

        self.assertEqual(unsubscribe.call_count, 0)

    @mock.patch("corehq.apps.registration.utils.safe_unsubscribe_user_from_mailchimp_list")
    def test_handle_changed_mailchimp_email_other_user_not_subscribed(self, unsubscribe):
        """ Two users with the same email, other user is not subscribed, so unsubscribe """

        other_username = "shmoe@my-domain.commcarehq.org"
        other_couch_user = CommCareUser.create(self.domain, other_username, "passw3rd", email=self.email)
        other_couch_user.subscribed_to_commcare_users = False
        other_couch_user.email_opt_out = True
        other_couch_user.save()

        new_email = "newemail@example.com"

        handle_changed_mailchimp_email(self.couch_user, self.email, new_email)

        expected_call_args = [mock.call(self.couch_user, settings.MAILCHIMP_COMMCARE_USERS_ID, email=self.email),
                              mock.call(self.couch_user, settings.MAILCHIMP_MASS_EMAIL_ID, email=self.email)]

        self.assertEqual(unsubscribe.call_count, 2)
        self.assertItemsEqual(unsubscribe.call_args_list, expected_call_args)

    @mock.patch("corehq.apps.registration.utils.safe_unsubscribe_user_from_mailchimp_list")
    def test_handle_changed_mailchimp_email_same_email_alternate_subscriptions(self, unsubscribe):
        """ Two users with the same email, other user is subscribed to opposite lists """
        self.couch_user.email_opt_out = True
        self.couch_user.save()

        # User subscribed to mass email list
        other_username = "shmoe@my-domain.commcarehq.org"
        other_couch_user = CommCareUser.create(self.domain, other_username, "passw3rd", email=self.email)
        other_couch_user.subscribed_to_commcare_users = False
        other_couch_user.email_opt_out = False
        other_couch_user.save()

        new_email = "newemail@example.com"

        handle_changed_mailchimp_email(self.couch_user, self.email, new_email)

        expected_call_args = [mock.call(self.couch_user, settings.MAILCHIMP_MASS_EMAIL_ID, email=self.email)]

        self.assertEqual(unsubscribe.call_count, 1)
        self.assertItemsEqual(unsubscribe.call_args_list, expected_call_args)
