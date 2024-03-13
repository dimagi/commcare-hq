from django.test import SimpleTestCase
from corehq.apps.reports.forms import EmailReportForm


class EmailReportFormTests(SimpleTestCase):
    def test_get_readable_errors_prefixes_label_for_field_specific_errors(self):
        form = EmailReportForm({'recipient_emails': ['invalid_email']})
        errors = form.get_readable_errors()
        self.assertEqual(errors, ['Additional Recipients: Please enter only valid email addresses.'])

    def test_readable_errors_excludes_label_for_formwide_errors(self):
        form = EmailReportForm({'recipient_emails': [], 'send_to_owner': False})
        errors = form.get_readable_errors()
        self.assertEqual(errors, ['You must specify at least one valid recipient'])
