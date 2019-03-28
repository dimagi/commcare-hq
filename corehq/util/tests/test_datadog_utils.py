from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
from corehq.util.datadog.utils import sanitize_url, get_url_group, bucket_value


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


@generate_cases([
    ('/', 'other'),
    ('/a/*/api', 'api'),
    ('/a/domain', 'other'),
    ('/1/2/3/4', 'other'),
    ('/a/*/cloudcare', 'cloudcare'),
], DatadogUtilsTest)
def test_url_group(self, url, group):
    self.assertEqual(get_url_group(url), group)


@generate_cases([
    (0, (1, 2, 5), '', 'lt_001'),
    (1, (1, 2, 5), '', 'lt_002'),
    (6, (1, 2, 5), '', 'over_005'),
    (101, (1, 2, 100), 's', 'over_100s'),
    (4, (1, 2, 5), 's', 'lt_005s'),
    (4, (1, 2, 5, 1000), 's', 'lt_0005s'),
    (6, (1, 2, 5, 1000, 43000), 's', 'lt_01000s'),
    (3000, (1, 2, 5, 1000), 's', 'over_1000s'),
], DatadogUtilsTest)
def test_bucket_value(self, value, buckets, unit, expected):
    self.assertEqual(bucket_value(value, buckets, unit), expected)
