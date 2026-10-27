import pytest
from django.test import SimpleTestCase

from corehq.util.strings import get_masked_email, get_masked_string


class TestGetMaskedString(SimpleTestCase):
    def test_handles_empty_string(self):
        result = get_masked_string('')
        self.assertEqual(result, '')

    def test_standard_case_with_defaults(self):
        result = get_masked_string('abcdef')
        self.assertEqual(result, 'abc***')

    def test_with_custom_mask_character(self):
        result = get_masked_string('abcdef', mask_character='#')
        self.assertEqual(result, 'abc###')

    def test_with_custom_reveal_length(self):
        result = get_masked_string('abcdef', reveal_length=2)
        self.assertEqual(result, 'ab****')

    def test_string_shorter_than_reveal_length(self):
        result = get_masked_string('ab', reveal_length=3)
        self.assertEqual(result, 'ab')

    def test_reverse_reveal(self):
        result = get_masked_string('abcdef', reverse_reveal=True)
        self.assertEqual(result, '***def')

    def test_reverse_reveal_string_shorter_than_reveal_length(self):
        result = get_masked_string('ab', reveal_length=3, reverse_reveal=True)
        self.assertEqual(result, 'ab')


@pytest.mark.parametrize('email, expected', [
    ('clifford@example.com', 'c*******@example.com'),
    ('cliff"@ford"@example.com', 'c***********@example.com')
])
def test_get_masked_email(email, expected):
    assert get_masked_email(email) == expected
