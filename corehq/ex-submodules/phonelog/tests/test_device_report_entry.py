from unittest import TestCase

from corehq.util.test_utils import generate_cases
from phonelog.utils import _get_type_from_log


class TestUtils(TestCase):
    pass


@generate_cases([
    (None, None),
    ("", ""),
    ("short", "short"),
    ("longer_than_the_limit_of_32_chars", "longer_than_the_limit_of_32_ch.."),
    ("org.commcare.short", "short"),
    ("org.commcare.long.ClassNameThatIsLongerThanTheLimit", "ClassNameThatIsLongerThanTheLi.."),
], TestUtils)
def test_get_type_from_log(self, type_, expected):
    self.assertEqual(_get_type_from_log({"type": type_}), expected)
