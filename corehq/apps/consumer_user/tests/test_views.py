
from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode


from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)


def register_url(invitation):
    return reverse(
        'consumer_user:register',
        kwargs={'signed_invitation_id': invitation.signature()}
    )


def login_accept_url(invitation):
    return reverse(
        'consumer_user:login_with_invitation',
        kwargs={'signed_invitation_id': invitation.signature()}
    )


class RegisterTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:login')
        self.client = Client()

    def tearDown(self):
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def test_register_get(self):
        invitation = ConsumerUserInvitation.objects.create(
            case_id='1', domain='1', invited_by='I', email='a@a.com'
        )
        register_uri = register_url(invitation)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(invitation.accepted)

    def test_register_consumer(self):
        email = 'a@a.com'
        invitation = ConsumerUserInvitation.objects.create(
            case_id='2', domain='1', demographic_case_id='3', invited_by='I', email=email
        )
        register_uri = register_url(invitation)
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
        invitation = ConsumerUserInvitation.objects.create(case_id='3', domain='1', invited_by='I', email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation)
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
        invitation = ConsumerUserInvitation.objects.create(case_id='4', domain='1', invited_by='I', email=email)
        register_uri = register_url(invitation)
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
        invitation = ConsumerUserInvitation.objects.create(
            case_id='5', domain='1', invited_by='I', email='a@a.com', accepted=True
        )
        register_uri = register_url(invitation)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 302)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')

    def test_register_get_webuser(self):
        email = 'a6@a6.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='6', domain='1', invited_by='I', email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 302)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')
        self.assertFalse(invitation.accepted)

    def test_register_invalid_invitation(self):
        register_uri = reverse(
            'consumer_user:register',
            kwargs={'signed_invitation_id': TimestampSigner().sign(urlsafe_base64_encode(b'1000'))}
        )
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateNotUsed(response, 'consumer_user/signup.html')


class LoginTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:login')
        self.homepage_url = reverse('consumer_user:homepage')
        self.client = Client()

    def tearDown(self):
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

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
        invitation = ConsumerUserInvitation.objects.create(case_id='6', domain='1', invited_by='I', email=email)
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'consumer_user_login_view-current_step': 'auth',
        }
        response = self.client.post(login_accept_url(invitation), post_data)
        self.assertEqual(response.status_code, 302)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertRedirects(response, self.homepage_url)
