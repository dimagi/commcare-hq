import sys
from io import StringIO

from testil import Regex, eq, replattr

from .. import profile


def test_profile_decorator():
    output = StringIO()
    args = []

    @profile
    def func(arg):
        args.append(arg)

    with replattr(sys.stderr, "write", output.write):
        func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"test_decorators.py:\d+\(func\)"))


def test_profile_decorator_with_options():
    output = StringIO()
    args = []

    @profile(stream=output)
    def func(arg):
        args.append(arg)

    func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"test_decorators.py:\d+\(func\)"))


def test_profile_contextmanager():
    output = StringIO()
    args = []

    def func(arg):
        with profile(stream=output):
            args.append(arg)

    func(1)
    eq(args, [1])
    eq(output.getvalue(), Regex(r"\{method 'append' of 'list' objects\}"))
