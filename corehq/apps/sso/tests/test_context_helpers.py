import datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.sso.utils.context_helpers import (
    render_multiple_to_strings,
    get_idp_cert_expiration_email_context,
)
from corehq.apps.sso.tests.base_test import BaseIdPTest


class TestSimpleIdPContextHelpers(SimpleTestCase):

    @patch("corehq.apps.sso.utils.context_helpers.render_to_string")
    def test_render_multiple_to_strings(self, mock_render):
        context = object()
        for templates in (["t0"], ["t1", "t2"]):
            list(render_multiple_to_strings(context, *templates))
            self.assertEqual(mock_render.call_count, len(templates))
            mock_render.assert_called_with(templates[-1], context)
            mock_render.reset_mock()


class TestIdPContextHelpers(BaseIdPTest):

    def test_get_idp_cert_expiration_email_context(self):
        self.idp.date_idp_cert_expiration = datetime.datetime.utcnow()
        self.idp.save()
        self.assertSetEqual(set(get_idp_cert_expiration_email_context(self.idp)),
                            {"subject", "from", "to", "bcc", "html", "plaintext"})
