"""Test utilities

Code in this package may import test-only dependencies. Therefore this
package should not be imported by non-test code.

The intent of this package is to become a better organized home of most
things that currently live in `corehq.util.test_utils`. Note that there
are some things in that module that are imported by non-test code; they
should not be moved here.
"""
import difflib


def check_output(expected, actual, checker, extension):
    # snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
    if isinstance(expected, bytes):
        expected = expected.decode('utf-8')
    if isinstance(actual, bytes):
        actual = actual.decode('utf-8')
    if not checker.check_output(expected, actual, 0):
        original_message = message = "{} mismatch\n\n".format(extension.upper())
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile='want.{}'.format(extension),
            tofile='got.{}'.format(extension)
        )
        for line in diff:
            message += line
        if message != original_message:
            # check that there was actually a diff, because checker.check_output
            # doesn't work with unicode characters in xml node names
            raise AssertionError(message)
