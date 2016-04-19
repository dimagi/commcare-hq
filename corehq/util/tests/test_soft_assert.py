import math
from django.test import SimpleTestCase, RequestFactory
from django.test.utils import override_settings
from corehq.util.log import get_sanitized_request_repr
from corehq.util.soft_assert.core import SoftAssert
from corehq.util.soft_assert.api import _send_message, soft_assert
from corehq.util.cache_utils import ExponentialBackoff
from corehq.util.test_utils import softer_assert


class SoftAssertTest(SimpleTestCase):

    def setUp(self):
        self.infos = []
        self.soft_assert = SoftAssert(
            send=self.send,
            use_exponential_backoff=False
        )

    def send(self, info):
        self.infos.append(info)

    def hypotenuse(self, a, b):
        return self.square_root(self.squared(a) + self.squared(b))

    def square_root(self, x):
        if not self.soft_assert(isinstance(x, float)):
            x = float(x)
        return math.sqrt(x)

    def squared(self, x):
        if not self.soft_assert(isinstance(x, float)):
            x = float(x)
        return x * x

    @softer_assert
    def test_soft_assert(self):
        self.assertEqual(self.hypotenuse('3.0', 4), 5.0)
        self.assertEqual(len(self.infos), 2)
        key0 = self.infos[0].key
        key1 = self.infos[1].key
        self.assertEqual(self.hypotenuse('3.0', 4), 5.0)
        self.assertEqual(len(self.infos), 4)
        self.assertEqual(self.infos[2].key, key0, '\n{}\n{}'.format(
            self.infos[0].traceback,
            self.infos[2].traceback,
        ))
        self.assertEqual(self.infos[3].key, key1, '\n{}\n{}'.format(
            self.infos[1].traceback,
            self.infos[3].traceback,
        ))
        self.assertEqual(self.infos[0].line,
                         'if not self.soft_assert(isinstance(x, float)):')
        self.assertEqual(self.infos[1].line,
                         'if not self.soft_assert(isinstance(x, float)):')
        self.assertEqual(self.infos[2].line,
                         'if not self.soft_assert(isinstance(x, float)):')
        self.assertEqual(self.infos[3].line,
                         'if not self.soft_assert(isinstance(x, float)):')

    @softer_assert
    def test_message_newlines(self):
        _soft_assert = soft_assert(notify_admins=True)
        _soft_assert(False, u"don't\ncrash")


class SoftAssertHelpersTest(SimpleTestCase):
    def test_number_is_power_of_two(self):
        powers_of_two = [2**i for i in range(10)]
        for n in range(100):
            actual = ExponentialBackoff._number_is_power_of_two(n)
            expected = n in powers_of_two
            self.assertEqual(actual, expected,
                             '_number_is_power_of_two: {}'.format(actual))

    @softer_assert
    @override_settings(DEBUG=False)
    def test_request_sanitization(self):
        raw_request = RequestFactory().post('/accounts/login/', {'username': 'sreddy', 'password': 'mypass'})
        # Django setting to mark request sensitive
        raw_request.sensitive_post_parameters = '__ALL__'
        santized_request = get_sanitized_request_repr(raw_request)

        # raw request exposes password
        self.assertTrue('mypass' in str(raw_request))

        # sanitized_request should't expose password
        self.assertFalse('mypass' in santized_request)
        self.assertTrue('*******' in santized_request)

    @softer_assert
    def test_send_message(self):

        def test1(subject, message):
            self.assertRegexpMatches(subject,
                                     r"Soft Assert: \[\w+\] This should fail")
            things_that_should_show_up_in_message = [
                r"Message: This should fail",
                r"Traceback:",
                r'File ".*corehq/util/tests/test_soft_assert.py", line \d+, in test_send_message',
                r"self\.soft_assert\(False, 'This should fail'\)",
                r"Occurrences to date: 1",
            ]
            for thing in things_that_should_show_up_in_message:
                self.assertRegexpMatches(
                    message,
                    thing,
                    '{!r}\ndoes not match\n---\n{}---\n'.format(thing, message)
                )

        def test2(subject, message):
            self.assertRegexpMatches(
                subject,
                r'Soft Assert: \[\w+\] None',
            )
            things_that_should_show_up_in_message = [
                r"Message: None",
                r"Traceback:",
                r'File ".*corehq/util/tests/test_soft_assert.py", line \d+, in test_send_message',
                r"self\.soft_assert\(False\)",
                r"Occurrences to date: 1",
            ]
            for thing in things_that_should_show_up_in_message:
                self.assertRegexpMatches(
                    message,
                    thing,
                    '{!r}\ndoes not match\n---\n{}---\n'.format(thing, message)
                )

        tests = iter([test1, test2])

        def backend(subject, message):
            test_ = tests.next()
            test_(subject, message)

        self.soft_assert = SoftAssert(
            send=lambda info: _send_message(info, backend=backend),
        )
        # sent to test1
        self.soft_assert(False, 'This should fail')
        # sent to test2
        self.soft_assert(False)
