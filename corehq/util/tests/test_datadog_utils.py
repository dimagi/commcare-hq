from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
from corehq.util.datadog.utils import sanitize_url


class DatadogUtilsTest(SimpleTestCase):
    """Tests datadog utility functions"""


@generate_cases([
    (
        '/a/uth-rhd/api/a26f2e21-5f24-48b6-b283-200a21f79bb6/20150922T034026.MP4',
        '/a/*/api/*/20150922T034026.MP4'
    ),
    ('/a/ben/modules-1/forms-2/uuid:abc123/', '/a/*/modules-*/forms-*/uuid:*/')
], DatadogUtilsTest)
def test_sanitize_url(self, url, sanitized):
    self.assertEqual(sanitize_url(url), sanitized)
