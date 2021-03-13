import uuid

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from mock import patch

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_CASE_TYPE,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.apps.data_interfaces.tests.util import create_case
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.tests.utils import FormProcessorTestUtils


def register_url(invitation):
    return reverse('consumer_user:consumer_user_register',
                   kwargs={'invitation': TimestampSigner().sign(
                       urlsafe_base64_encode(force_bytes(invitation))
                   )})


def login_accept_url(invitation):
    return reverse('consumer_user:consumer_user_login_with_invitation',
                   kwargs={'invitation': TimestampSigner().sign(
                       urlsafe_base64_encode(force_bytes(invitation))
                   )})


class RegisterTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:consumer_user_login')
        self.client = Client()

    def tearDown(self):
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_register_get(self):
        invitation = ConsumerUserInvitation.objects.create(case_id='1', domain='1', invited_by='I',
                                                           email='a@a.com')
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consumer_user/signup.html')
        self.assertFalse(invitation.accepted)

    def test_register_consumer(self):
        email = 'a@a.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='2', domain='1', demographic_case_id='3',
                                                           invited_by='I', email=email)
        register_uri = register_url(invitation.id)
        self.assertFalse(invitation.accepted)
        post_data = {
            'first_name': 'First',
            'last_name': 'Last',
            'email': email,
            'password': 'password',
        }
        self.assertQuerysetEqual(User.objects.filter(username=post_data.get('email')), [])
        response = self.client.post(register_uri, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.login_url)
        created_user = User.objects.get(username=post_data.get('email'))
        consumer_user = ConsumerUser.objects.get(user=created_user)
        user_case = ConsumerUserCaseRelationship.objects.get(consumer_user=consumer_user)
        invitation.refresh_from_db()
        self.assertEqual(user_case.case_id, invitation.demographic_case_id)
        self.assertEqual(user_case.domain, invitation.domain)
        self.assertTrue(invitation.accepted)

    def test_register_existing_user(self):
        email = 'a1@a1.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='3', domain='1', invited_by='I',
                                                           email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation.id)
        self.assertFalse(invitation.accepted)
        post_data = {
            'first_name': 'First',
            'last_name': 'Last',
            'email': email,
            'password': 'password',
        }
        self.assertNotEqual(User.objects.filter(username=email).count(), 0)
        response = self.client.get(register_uri, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, register_uri.replace('signup', 'login'))

    def test_register_different_email(self):
        email = 'a2@a2.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='4', domain='1', invited_by='I',
                                                           email=email)
        register_uri = register_url(invitation.id)
        self.assertFalse(invitation.accepted)
        post_data = {
            'first_name': 'First',
            'last_name': 'Last',
            'email': 'ae@different.in',
            'password': 'password',
        }
        response = self.client.post(register_uri + '?create_user=1', post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.login_url)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)

    def test_register_accepted_invitation(self):
        invitation = ConsumerUserInvitation.objects.create(case_id='5', domain='1', invited_by='I',
                                                           email='a@a.com', accepted=True)
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 302)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')

    def test_register_get_webuser(self):
        email = 'a6@a6.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='6', domain='1', invited_by='I',
                                                           email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 302)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')
        self.assertFalse(invitation.accepted)

    def test_register_invalid_invitation(self):
        register_uri = register_url(1000)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')


class LoginTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:consumer_user_login')
        self.homepage_url = reverse('consumer_user:consumer_user_homepage')
        self.client = Client()

    def tearDown(self):
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_login_get(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consumer_user/p_login.html')

    def test_login_post(self):
        email = 'log@log.in'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        ConsumerUser.objects.create(user=user)
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'consumer_user_login_view-current_step': 'auth',
        }
        response = self.client.post(self.login_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.homepage_url)

    def test_login_accept_invitation(self):
        email = 'log1@log1.in'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        ConsumerUser.objects.create(user=user)
        invitation = ConsumerUserInvitation.objects.create(case_id='6', domain='1', invited_by='I',
                                                           email=email)
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'consumer_user_login_view-current_step': 'auth',
        }
        response = self.client.post(login_accept_url(invitation.id), post_data)
        self.assertEqual(response.status_code, 302)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertRedirects(response, self.homepage_url)


class SignalTestCase(TestCase):

    def setUp(self):
        self.domain = 'consumer-invitation-test'
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_method_send_email(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                                  relationship=CASE_INDEX_EXTENSION)
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {'email': 'testing@testing.in'}
                    }
                )
            )
            # Creating new comm care case creates a new ConsumerUserInvitation
            case = result[0]
            customer_invitation = ConsumerUserInvitation.objects.get(case_id=case.case_id, domain=case.domain)
            self.assertEqual(customer_invitation.email, case.get_case_property('email'))
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Updating the case properties other than email should not create a new invitation
            update_case(self.domain, case.case_id,
                        case_properties={'contact_phone_number': '12345'})
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Updating the case again with a changed email address creates a new invitation
            update_case(self.domain, case.case_id,
                        case_properties={'email': 'email@changed.in'})
            self.assertEqual(ConsumerUserInvitation.objects.count(), 2)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 2)
            # Updating the case again with status other than sent or accepted should send email again
            update_case(self.domain, case.case_id,
                        case_properties={CONSUMER_INVITATION_STATUS: 'resend'})
            self.assertEqual(ConsumerUserInvitation.objects.count(), 3)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 3)
            # Closing the case should make invitation inactive
            update_case(self.domain, case.case_id, None, True)
            self.assertEqual(ConsumerUserInvitation.objects.count(), 3)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 0)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=False).count(),
                             ConsumerUserInvitation.objects.count())
            self.assertEqual(send_html_email_async.call_count, 3)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_method_send_email_other_casetype(self):
        invitation_count = ConsumerUserInvitation.objects.count()
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async, create_case(
            self.domain,
            'person',
            owner_id='comm_care',
        ) as case:
            self.assertEqual(ConsumerUserInvitation.objects.filter(case_id=case.case_id,
                                                                   domain=case.domain).count(), 0)
            self.assertEqual(ConsumerUserInvitation.objects.count(), invitation_count)
            send_html_email_async.assert_not_called()


class DomainsAndCasesTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.url = reverse('consumer_user:domain_and_cases_list')

    def tearDown(self):
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_domains_and_cases_get(self):
        email = 'b@b.com'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        consumer_user = ConsumerUser.objects.create(user=user)
        ConsumerUserCaseRelationship.objects.create(consumer_user=consumer_user, case_id='1', domain='d1')
        ConsumerUserCaseRelationship.objects.create(consumer_user=consumer_user, case_id='1', domain='d2')
        self.client.login(username=email, password=password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consumer_user/domains_and_cases.html')
        self.assertEqual(response.context['domains_and_cases'],
                         [{'domain': 'd2', 'case_id': '1'}, {'domain': 'd1', 'case_id': '1'}])

    def test_domains_and_cases_no_data(self):
        email = 'b1@b1.com'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        ConsumerUser.objects.create(user=user)
        self.client.login(username=email, password=password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consumer_user/domains_and_cases.html')
        self.assertEqual(response.context['domains_and_cases'], [])

    def test_domains_and_cases_no_user_logged_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_domains_and_cases_user_logged_in_no_consumer_user(self):
        email = 'user@noconsumer.in'
        password = 'password'
        User.objects.create_user(username=email, email=email, password=password)
        self.client.login(username=email, password=password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


class ChangeContactDetailsTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.url = reverse('consumer_user:change_contact_details')

    def tearDown(self):
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_change_contact_details_get(self):
        email = 'b2@b2.com'
        password = 'password'
        first_name = 'first'
        last_name = 'last'
        user = User.objects.create_user(username=email, email=email,
                                        password=password, first_name=first_name,
                                        last_name=last_name)
        ConsumerUser.objects.create(user=user)
        self.client.login(username=email, password=password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed('consumer_user/change_contact_details.html')

    def test_change_contact_details_post(self):
        email = 'b3@b3.com'
        password = 'password'
        first_name = 'first'
        last_name = 'last'
        user = User.objects.create_user(username=email, email=email,
                                        password=password, first_name=first_name,
                                        last_name=last_name)
        ConsumerUser.objects.create(user=user)
        self.client.login(username=email, password=password)
        post_data = {
            'first_name': 'first_name',
            'last_name': 'last_name'
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        new_user = User.objects.get(username=email)
        self.assertEqual(new_user.first_name, 'first_name')
        self.assertEqual(new_user.last_name, 'last_name')

    def test_change_contact_details_no_user_logged_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_change_contact_details_user_logged_in_no_consumer_user(self):
        email = 'user@noconsumer.in'
        password = 'password'
        first_name = 'first'
        last_name = 'last'
        User.objects.create_user(username=email, email=email,
                                 password=password, first_name=first_name,
                                 last_name=last_name)
        self.client.login(username=email, password=password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
