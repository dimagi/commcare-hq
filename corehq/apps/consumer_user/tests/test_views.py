from django.test import TestCase
from django.test.client import Client
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from django.urls import reverse
from django.contrib.auth.models import User
from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from mock import patch
from corehq.form_processor.models import CommCareCaseSQL
from corehq.apps.consumer_user.signals import send_email_case_changed_receiver


def register_url(invitation):
    return reverse('consumer_user:patient_register',
                   kwargs={'invitation': urlsafe_base64_encode(force_bytes(invitation))})


class RegisterTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:patient_login')
        self.client = Client()

    def test_register_get(self):
        invitation = ConsumerUserInvitation.objects.create(case_id='1', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email='a@a.com')
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'signup.html')
        self.assertFalse(invitation.accepted)
        self.assertFalse(response.context['existing_user'])

    def test_register_consumer(self):
        email = 'a@a.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='2', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email=email)
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
        user_case = ConsumerUserCaseRelationship.objects.get(case_user=consumer_user)
        invitation.refresh_from_db()
        self.assertEqual(user_case.case_id, invitation.case_id)
        self.assertEqual(user_case.domain, invitation.domain)
        self.assertTrue(invitation.accepted)

    def test_register_webuser(self):
        email = 'a1@a1.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='3', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
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
        self.assertNotEqual(User.objects.filter(username=post_data.get('email')).count(), 0)
        response = self.client.post(register_uri, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.login_url)
        created_user = User.objects.get(username=post_data.get('email'))
        consumer_user = ConsumerUser.objects.get(user=created_user)
        user_case = ConsumerUserCaseRelationship.objects.get(case_user=consumer_user)
        invitation.refresh_from_db()
        self.assertEqual(user_case.case_id, invitation.case_id)
        self.assertEqual(user_case.domain, invitation.domain)
        self.assertTrue(invitation.accepted)

    def test_register_different_email(self):
        email = 'a2@a2.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='4', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email=email)
        register_uri = register_url(invitation.id)
        self.assertFalse(invitation.accepted)
        post_data = {
            'first_name': 'First',
            'last_name': 'Last',
            'email': 'a@a.in',
            'password': 'password',
        }
        response = self.client.post(register_uri, post_data)
        self.assertEqual(response.status_code, 400)

    def test_register_accepted_invitation(self):
        invitation = ConsumerUserInvitation.objects.create(case_id='5', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email='a@a.com', accepted=True)
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 302)
        self.assertTemplateNotUsed(response, 'signup.html')

    def test_register_get_webuser(self):
        email = 'a6@a6.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='6', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation.id)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'signup.html')
        self.assertTrue(response.context['existing_user'])
        self.assertFalse(invitation.accepted)

    def test_register_webuser_wrong_password(self):
        email = 'a7@a7.com'
        invitation = ConsumerUserInvitation.objects.create(case_id='7', domain='1', invited_by='I',
                                                           invited_on='2021-02-09 17:17:32.229524+00',
                                                           email=email)
        User.objects.create_user(username=email, email=email, password='password')
        register_uri = register_url(invitation.id)
        self.assertFalse(invitation.accepted)
        post_data = {
            'first_name': 'First',
            'last_name': 'Last',
            'email': email,
            'password': 'wrong_password',
        }
        self.assertNotEqual(User.objects.filter(username=post_data.get('email')).count(), 0)
        response = self.client.post(register_uri, post_data)
        self.assertEqual(response.status_code, 400)

    def test_register_invalid_invitation(self):
        register_uri = register_url(1000)
        response = self.client.get(register_uri)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateNotUsed(response, 'signup.html')


class LoginTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.login_url = reverse('consumer_user:patient_login')
        self.homepage_url = reverse('consumer_user:patient_homepage')
        self.client = Client()

    def test_login_get(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'two_factor/core/login.html')

    def test_login_post(self):
        email = 'log@log.in'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        ConsumerUser.objects.create(user=user)
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'patient_login_view-current_step': 'auth',
        }
        response = self.client.post(self.login_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.homepage_url)

    def test_login_post_no_consumer_user(self):
        email = 'log1@log1.in'
        password = 'password'
        User.objects.create_user(username=email, email=email, password=password)
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'patient_login_view-current_step': 'auth',
        }
        response = self.client.post(self.login_url, post_data)
        self.assertEqual(response.status_code, 400)

    def test_login_post_no_user(self):
        email = 'wrong@wrong.in'
        password = 'password'
        post_data = {
            'auth-username': email,
            'auth-password': password,
            'patient_login_view-current_step': 'auth',
        }
        response = self.client.post(self.login_url, post_data)
        self.assertEqual(response.status_code, 400)

    def test_login_web_user_logged_in(self):
        email = 'web@consumer.in'
        password = 'password'
        user = User.objects.create_user(username=email, email=email, password=password)
        ConsumerUser.objects.create(user=user)
        self.client.login(username=email, password=password)
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.homepage_url)

    def test_login_web_user_logged_in_no_consumer_user(self):
        email = 'web@noconsumer.in'
        password = 'password'
        User.objects.create_user(username=email, email=email, password=password)
        self.client.login(username=email, password=password)
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 400)


class SignalTestCase(TestCase):

    def setUp(self):
        self.case_sql = CommCareCaseSQL(case_id="case_id", domain="domain", opened_by="in@invite.com")
        self.invitation_count = ConsumerUserInvitation.objects.count()

    def test_method_send_email(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as async_task:
            send_email_case_changed_receiver(None, self.case_sql)
            self.assertEqual(ConsumerUserInvitation.objects.count(), self.invitation_count + 1)
            async_task.assert_called_once()
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as do_not_send_email:
            send_email_case_changed_receiver(None, self.case_sql)
            self.assertEqual(ConsumerUserInvitation.objects.count(), self.invitation_count + 1)
            do_not_send_email.assert_not_called()
