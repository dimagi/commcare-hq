# encoding: utf-8
from __future__ import absolute_import
from django.test import SimpleTestCase
from django.test.utils import override_settings

import corehq.apps.domain.forms as forms
from corehq.util.test_utils import generate_cases

# 1 Special Character, 1 Number, 1 Capital Letter with the length of Minimum 8
tests = [
    (u'abcdefg', -2),
    (u'ABCDEFG', -1),
    (u'1234567', -1),
    (u'!@#$%^&', -1),
    (u'abcdef*', -1),
    (u'Abcdef*', 0),
    (u'0bcdef*', 0),
    (u'Ab0000*', 1),
    (u'AB0000*', 1),

    (u'abcdefgh', -1),
    (u'ABCDEFGH', 0),
    (u'12345678', 0),
    (u'!@#$%^&*', 0),
    (u'abcdefg*', 0),
    (u'Abcdefg*', 1),
    (u'0bcdefg*', 1),
    (u'åb0000g*', 1),  # lowercase unicode character does not count
    (u'Ab0000g*', 2),
    (u'AB0000G*', 2),
    (u'Åb0000g*', 2),  # uppercase unicode character
]


class TestLegacyPassword(SimpleTestCase):
    pass


@generate_cases(tests, TestLegacyPassword)
def test_legacy_get_password_strength_score(self, password, expected_score):
    strength = forms.legacy_get_password_strength(password)
    self.assertEqual(strength['score'], expected_score)


@generate_cases([t[:1] for t in tests if t[1] < 2], TestLegacyPassword)
def test_legacy_clean_password_failures(self, password):
    with override_settings(ENABLE_DRACONIAN_SECURITY_FEATURES=True):
        with self.assertRaises(forms.forms.ValidationError):
            forms.clean_password(password)


@generate_cases([t[:1] for t in tests if t[1] >= 2], TestLegacyPassword)
def test_legacy_clean_password_pass(self, password):
    with override_settings(ENABLE_DRACONIAN_SECURITY_FEATURES=True):
        self.assertEqual(forms.clean_password(password), password)
