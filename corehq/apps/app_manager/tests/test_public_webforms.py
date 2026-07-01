from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    PublicFormSession,
    PublicWebform,
)
from corehq.apps.users.util import PUBLIC_USER_ID


class PublicFormSessionTests(SimpleTestCase):

    def test_session_username(self):
        webform = PublicWebform(domain='public-forms-domain')
        session = PublicFormSession(public_webform=webform)
        assert session.session_username == (
            f'{PUBLIC_USER_ID}{session.id.hex}@public-forms-domain.commcarehq.org'
        )
