from django.test import TestCase

from corehq.apps.email.forms import EmailSMTPSettingsForm


class EmailSMTPSettingsFormTests(TestCase):

    def test_valid_form(self):
        form_data = EmailSMTPSettingsFormTests._get_valid_form_data()
        form = EmailSMTPSettingsForm(data=form_data)

        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        form_data = EmailSMTPSettingsFormTests._get_valid_form_data()
        form_data.update({'username': ''})

        form = EmailSMTPSettingsForm(data=form_data)

        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_clean_port(self):
        form_data = EmailSMTPSettingsFormTests._get_valid_form_data()

        # Valid port number
        form = EmailSMTPSettingsForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Invalid port number, less than lower bound
        form_data.update({'port': 0})

        form = EmailSMTPSettingsForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('port', form.errors)

        # Invalid port number, more than upper bound
        form_data.update({'port': 65536})

        form = EmailSMTPSettingsForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('port', form.errors)

    def test_clean_from_email(self):
        form_data = EmailSMTPSettingsFormTests._get_valid_form_data()

        # Valid email address
        form = EmailSMTPSettingsForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Invalid email address
        form_data.update({'from_email': 'invalid_email'})

        form = EmailSMTPSettingsForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('from_email', form.errors)

    @staticmethod
    def _get_valid_form_data():
        return {
            'username': 'testuser',
            'plaintext_password': 'testpassword',
            'server': 'smtp.example.com',
            'port': 587,
            'from_email': 'test@example.com',
            'use_this_gateway': True,
            'use_tracking_headers': True,
            'sns_secret': 'secret_key'
        }
