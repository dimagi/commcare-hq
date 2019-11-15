import re
import sys
from io import StringIO

from corehq.util.teeout import tee_output
from testil import assert_raises, eq


def test_tee_output():
    fileobj = StringIO()
    fake = fakesys()
    with assert_raises(Error), tee_output(fileobj, sys=fake):
        print("testing...", file=fake.stdout)
        fake.stderr.write("fail.\n")
        raise Error("stop")
    eq(fake.stdout.getvalue(), "testing...\n")
    eq(fake.stderr.getvalue(), "fail.\n")
    eq(sanitize_tb(fileobj.getvalue()),
        "testing...\n"
        "fail.\n"
        "Traceback (most recent call last):\n"
        "  ...\n"
        "corehq.util.tests.test_teeout.Error: stop\n")


def test_tee_output_with_KeyboardInterrupt():
    fileobj = StringIO()
    fake = fakesys()
    with assert_raises(KeyboardInterrupt), tee_output(fileobj, sys=fake):
        raise KeyboardInterrupt("errrt")
    eq(fake.stdout.getvalue(), "")
    eq(fake.stderr.getvalue(), "")
    eq(sanitize_tb(fileobj.getvalue()),
        "Traceback (most recent call last):\n"
        "  ...\n"
        "KeyboardInterrupt: errrt\n")


def test_tee_output_with_SystemExit():
    fileobj = StringIO()
    fake = fakesys()
    with assert_raises(SystemExit), tee_output(fileobj, sys=fake):
        raise SystemExit(1)
    eq(fake.stdout.getvalue(), "")
    eq(fake.stderr.getvalue(), "")
    eq(fileobj.getvalue(), "")


def fakesys():
    class fake(object):
        stdout = StringIO()
        stderr = StringIO()

        def exc_info():
            return sys.exc_info()

    return fake


def sanitize_tb(value):
    return re.sub(
        r"(Traceback .*:\n)(?:  .*\n)+",
        r"\1  ...\n",
        value,
        flags=re.MULTILINE,
    )


class Error(Exception):
    pass
