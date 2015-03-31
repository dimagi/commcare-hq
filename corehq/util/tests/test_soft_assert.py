from collections import defaultdict
import math
from django.test import SimpleTestCase
from corehq.util.soft_assert.core import SoftAssert
from corehq.util.soft_assert.api import _number_is_power_of_two, _send_message


class SoftAssertTest(SimpleTestCase):

    def setUp(self):
        self.infos = []
        self.counter = defaultdict(int)
        self.soft_assert = SoftAssert(
            send=self.send,
            incrementing_counter=self.incrementing_counter,
            should_send=self.should_send,
        )

    def send(self, info):
        self.infos.append(info)

    def should_send(self, count):
        return True

    def incrementing_counter(self, key):
        self.counter[key] += 1
        return self.counter[key]

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


class SoftAssertHelpersTest(SimpleTestCase):
    def test_number_is_power_of_two(self):
        powers_of_two = [2**i for i in range(10)]
        for n in range(100):
            actual = _number_is_power_of_two(n)
            expected = n in powers_of_two
            self.assertEqual(actual, expected,
                             '_number_is_power_of_two: {}'.format(actual))

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
            incrementing_counter=lambda key: 1,
            should_send=lambda count: True,
        )
        # sent to test1
        self.soft_assert(False, 'This should fail')
        # sent to test2
        self.soft_assert(False)
