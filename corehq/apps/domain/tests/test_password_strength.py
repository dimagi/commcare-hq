from django import forms
from django.test import SimpleTestCase, override_settings

from corehq.apps.domain.forms import clean_password


@override_settings(MINIMUM_PASSWORD_LENGTH=0, MINIMUM_ZXCVBN_SCORE=2)
class PasswordStrengthTest(SimpleTestCase):

    # Test zxcvbn library strength
    def test_weak_password_is_rejected(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[0])

    def test_almost_strong_enough_password_is_rejected(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[1])

    def test_exactly_required_strength_password_is_accepted(self):
        self.assert_good_password(PASSWORDS_BY_STRENGTH[2])

    def test_stronger_than_required_password_is_accepted(self):
        self.assert_good_password(PASSWORDS_BY_STRENGTH[3])

    @override_settings(MINIMUM_ZXCVBN_SCORE=3)
    def test_sensitivity_to_minimum_zxcvbn_score_setting_bad(self):
        self.assert_bad_password(PASSWORDS_BY_STRENGTH[2])

    @override_settings(MINIMUM_ZXCVBN_SCORE=3)
    def test_sensitivity_to_minimum_zxcvbn_score_setting_good(self):
        self.assert_good_password(PASSWORDS_BY_STRENGTH[3])

    # Test minimum password length
    @override_settings(MINIMUM_PASSWORD_LENGTH=8, MINIMUM_ZXCVBN_SCORE=0)
    def test_shorter_password_is_rejected(self):
        self.assert_bad_password("e3r4f")

    @override_settings(MINIMUM_PASSWORD_LENGTH=8, MINIMUM_ZXCVBN_SCORE=0)
    def test_exactly_minimum_length_password_is_accepted(self):
        self.assert_good_password("e3r4f4ed")

    @override_settings(MINIMUM_PASSWORD_LENGTH=8, MINIMUM_ZXCVBN_SCORE=0)
    def test_longer_than_minimum_length_password_is_accepted(self):
        self.assert_good_password("e3r4f4ed")

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
