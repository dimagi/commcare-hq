import textwrap

import mock
from django.test import SimpleTestCase

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.views import BugReportView
from corehq.apps.users.models import WebUser


class BugReportEmailTest(SimpleTestCase):

    @mock.patch.object(Domain, 'get_by_name')
    def test_simple(self, mock_Domain_get_by_name):
        mock_Domain_get_by_name.return_value = None
        email = BugReportView._get_email_message(
            post_params={
                'subject': 'I think I have a problem',
                'username': 'example@example.com',
                'domain': 'example',
                'url': 'https://www.commcarehq.org/a/droberts/dashboard/',
                'message': "I can't stop eating premixed pb&j by the jarful",
                'app_id': '',
                'cc': ' frankie@example.com,  angie@example.com ',
            },
            couch_user=WebUser(username='example@example.com', first_name='Eliezer', last_name='Xample'),
            uploaded_file=None,
        )
        self.assertEqual(email.body, textwrap.dedent("""
            username: example@example.com
            full name: Eliezer Xample
            domain: example
            url: https://www.commcarehq.org/a/droberts/dashboard/
            recipients: frankie@example.com, angie@example.com
            Message:

            I can't stop eating premixed pb&j by the jarful
        """).lstrip())
