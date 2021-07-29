from django import forms
from django.test import SimpleTestCase, override_settings

from corehq.apps.domain.forms import clean_password


class PasswordStrengthTest(SimpleTestCase):

    @override_settings(MINIMUM_ZXCVBN_SCORE=2)
    def test_score_0_password(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[0])

    @override_settings(MINIMUM_ZXCVBN_SCORE=2)
    def test_score_1_password(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[1])

    @override_settings(MINIMUM_ZXCVBN_SCORE=2)
    def test_score_2_password(self):
        self.assert_good_password(PASSWORDS_BY_STRENGTH[2])

    @override_settings(MINIMUM_ZXCVBN_SCORE=3)
    def test_sensitivity_to_minimum_zxcvbn_score_setting(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[2])

    def assert_good_password(self, password):
        self.assertEqual(clean_password(password), password)

    def assert_bad_password(self, password):
        with self.assertRaises(forms.ValidationError):
            clean_password(password)


PASSWORDS_BY_STRENGTH = {
    0: 's3cr3t',
    1: 'password7',
    2: 'aljfzpo',
    3: '1234mna823',
    4: ')(^#:LKNVA^',
}
