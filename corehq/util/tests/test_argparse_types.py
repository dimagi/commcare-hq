import re
from argparse import ArgumentParser
from contextlib import contextmanager
from io import StringIO
from unittest.mock import patch

from django.test import SimpleTestCase

from .. argparse_types import validate_range


class SystemExitError(Exception):
    pass


@contextmanager
def wrap_system_exit():
    stderr = StringIO()
    with patch("sys.stderr", stderr):
        try:
            yield stderr
        except SystemExit:
            raise SystemExitError(repr(stderr.getvalue()))


class TestValidateInteger(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.parser = ArgumentParser()

    def add_validated_arg(self, type, *val_args, **val_kw):
        self.parser.add_argument("value", type=type,
            action=validate_range(*val_args, **val_kw))

    def assert_parsed_value(self, argv, value):
        with wrap_system_exit():
            opts = self.parser.parse_args(argv)
        self.assertEqual(opts.value, value)

    def assert_parser_error(self, argv, err_suffix):
        with self.assertRaises(SystemExitError):
            with wrap_system_exit() as stderr:
                self.parser.parse_args(argv)
        err_msg = stderr.getvalue().strip().split("\n")[-1]
        self.assertRegexpMatches(err_msg, f": {re.escape(err_suffix)}$")

    def test_validate_range_int_gt5(self):
        self.add_validated_arg(int, gt=5)
        self.assert_parsed_value(["6"], 6)

    def test_validate_range_int_gt5_err(self):
        self.add_validated_arg(int, gt=5)
        self.assert_parser_error(["5"], "Must be greater than 5")

    def test_validate_range_int_lt5(self):
        self.add_validated_arg(int, lt=5)
        self.assert_parsed_value(["4"], 4)

    def test_validate_range_int_lt5_err(self):
        self.add_validated_arg(int, lt=5)
        self.assert_parser_error(["5"], "Must be less than 5")

    def test_validate_range_float_gt0(self):
        self.add_validated_arg(float, gt=0.0)
        self.assert_parsed_value(["1.5"], 1.5)

    def test_validate_range_float_gt0_err(self):
        self.add_validated_arg(float, gt=0.0)
        self.assert_parser_error(["-1.5"], "Must be greater than 0.0")
